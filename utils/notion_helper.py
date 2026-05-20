"""
Notion helper — upsert programme records via the Notion HTTP API (httpx).
All network calls are async; callers must be inside an async event loop.
"""

import logging
import hashlib

import httpx

from config import (
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
    NOTION_FIELD_MAP,
    AGENT_TO_NOTION_FIELD,
)

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _make_key(record: dict) -> str:
    raw = f"{record.get('institution','')}|{record.get('program','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _safe_str(val, default="N/A") -> str:
    if val is None or str(val).strip() == "":
        return default
    return str(val)


def _agent_field(notion_property: str) -> str:
    """Find the agent-output key that corresponds to a Notion property name."""
    for agent_key, notion_name in AGENT_TO_NOTION_FIELD.items():
        if notion_name == notion_property:
            return agent_key
    return notion_property.lower().replace(" ", "_")


class NotionSync:
    def __init__(self):
        self.token = NOTION_TOKEN
        raw_id = (NOTION_DATABASE_ID or "").replace("-", "")
        if len(raw_id) != 32:
            logger.warning(
                f"NOTION_DATABASE_ID is {len(raw_id)} chars (expected 32). "
                f"Check you copied the correct part from the URL."
            )
        self.db_id = raw_id
        self.existing_keys: dict[str, str] = {}

    async def validate_database(self, client: httpx.AsyncClient):
        """Fetch database metadata to verify access + dump schema."""
        logger.info(f"Validating Notion database: {self.db_id}")
        resp = await client.get(
            f"{NOTION_API_BASE}/databases/{self.db_id}"
        )
        if resp.status_code >= 400:
            logger.error(
                f"Cannot access database [{resp.status_code}]: {resp.text[:600]}"
            )
            return False
        db = resp.json()
        props = db.get("properties", {})
        logger.info(f"Database title: {_extract_text(db.get('title', []), 'title')}")
        logger.info(f"Database properties ({len(props)}):")
        for name, schema in props.items():
            logger.info(f"  {name}: {schema.get('type')}")
        return True

    async def load_existing(self, client: httpx.AsyncClient):
        """Fetch existing Notion pages and populate self.existing_keys."""
        if not self.token or not self.db_id:
            logger.warning("Missing NOTION_TOKEN or NOTION_DATABASE_ID")
            return
        logger.info(f"Querying pages from database: {self.db_id[:8]}...")
        try:
            cursor = None
            while True:
                body: dict = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor
                resp = await client.post(
                    f"{NOTION_API_BASE}/databases/{self.db_id}/query",
                    json=body,
                )
                if resp.status_code >= 400:
                    logger.error(
                        f"Notion query failed [{resp.status_code}]: {resp.text[:600]}"
                    )
                    resp.raise_for_status()
                data = resp.json()
                for page in data.get("results", []):
                    page_props = page.get("properties", {})
                    title_text = _extract_text(
                        page_props.get(NOTION_FIELD_MAP["Institution"], {}), "title"
                    )
                    prog_text = _extract_text(
                        page_props.get(NOTION_FIELD_MAP["Program"], {}), "rich_text"
                    )
                    key = hashlib.md5(
                        f"{title_text}|{prog_text}".encode()
                    ).hexdigest()
                    self.existing_keys[key] = page["id"]
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
            logger.info(f"Loaded {len(self.existing_keys)} existing pages")
        except Exception:
            logger.exception("Failed to load existing Notion pages")

    def _build_properties(self, record: dict) -> dict:
        """Map an agent record dict to Notion page properties."""
        props = {}

        # Title: Institution
        props[NOTION_FIELD_MAP["Institution"]] = {
            "title": [{"text": {"content": _safe_str(record.get("institution"))}}]
        }

        # Rich text fields
        rich_text_notion_fields = [
            "Program", "Website", "Requirement", "Project Link",
            "Region", "Country", "City", "Degree Type",
            "Orientation", "Preference", "Process",
            "Application Deadline", "Admission", "Study Period",
            "Tuition", "Language", "IELTS", "GRE", "GPA", "CV",
            "Core Requirements", "Field", "Notes", "Interview", "Summary",
        ]
        for notion_field in rich_text_notion_fields:
            notion_key = NOTION_FIELD_MAP.get(notion_field, notion_field)
            agent_key = _agent_field(notion_field)
            value = _safe_str(record.get(agent_key, ""))
            props[notion_key] = {
                "rich_text": [{"text": {"content": value}}]
            }

        # Date: Due Date
        due = record.get("due_date", "")
        if due and due != "N/A":
            props[NOTION_FIELD_MAP["Due Date"]] = {"date": {"start": due}}
        else:
            props[NOTION_FIELD_MAP["Due Date"]] = {"date": None}

        # Numbers
        props[NOTION_FIELD_MAP["Days to Prepare"]] = {
            "number": int(record.get("days_to_prepare", 0) or 0)
        }
        props[NOTION_FIELD_MAP["Importance"]] = {
            "number": int(record.get("importance", 5) or 5)
        }

        # Select: School
        school_val = record.get("school") or record.get("institution", "")
        props["School"] = {"select": {"name": _safe_str(school_val)}}

        return props

    async def _upsert_one(self, client: httpx.AsyncClient, record: dict):
        key = _make_key(record)
        try:
            properties = self._build_properties(record)
        except Exception:
            logger.exception(
                f"_build_properties failed for {record.get('program')}"
            )
            return False

        try:
            if key in self.existing_keys:
                resp = await client.patch(
                    f"{NOTION_API_BASE}/pages/{self.existing_keys[key]}",
                    json={"properties": properties},
                )
                if resp.status_code >= 400:
                    logger.error(
                        f"Notion PATCH failed [{resp.status_code}] "
                        f"for {record.get('program')}: {resp.text[:600]}"
                    )
                    resp.raise_for_status()
                logger.info(f"Updated: {record.get('program')}")
            else:
                resp = await client.post(
                    f"{NOTION_API_BASE}/pages",
                    json={
                        "parent": {"database_id": self.db_id},
                        "properties": properties,
                    },
                )
                if resp.status_code >= 400:
                    logger.error(
                        f"Notion POST failed [{resp.status_code}] "
                        f"for {record.get('program')}: {resp.text[:600]}"
                    )
                resp.raise_for_status()
                page_data = resp.json()
                self.existing_keys[key] = page_data["id"]
                logger.info(f"Created: {record.get('program')}")
            return True
        except Exception:
            logger.exception(
                f"Notion upsert failed for {record.get('program')}"
            )
            return False

    async def sync_all(self, records: list[dict]):
        if not records:
            return 0, 0
        logger.info(
            f"Syncing {len(records)} records to database: {self.db_id[:8]}..."
        )
        created, updated = 0, 0
        async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
            # 1) Validate database access + dump schema
            ok = await self.validate_database(client)
            if not ok:
                logger.error("Database validation failed — aborting sync")
                return 0, 0

            # 2) Load existing pages for dedup
            await self.load_existing(client)

            # 3) Upsert each record
            for rec in records:
                key = _make_key(rec)
                existed = key in self.existing_keys
                ok = await self._upsert_one(client, rec)
                if ok:
                    if existed:
                        updated += 1
                    else:
                        created += 1
        logger.info(f"Notion sync done: {created} created, {updated} updated")
        return created, updated


def _extract_text(prop_obj: dict, prop_type: str) -> str:
    if not prop_obj:
        return ""
    items = prop_obj.get(prop_type, [])
    return "".join(t.get("plain_text", "") for t in items)
