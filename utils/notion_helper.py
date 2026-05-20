"""
Notion helper — upsert programme records via the Notion HTTP API (httpx).
All network calls are async; callers must be inside an async event loop.

Key design:
- validate_database() reads the live schema and stores it as self.db_schema
- _build_properties() uses the live schema to emit the correct property
  structure for every field (title / rich_text / select / url / number / date)
- Fields that do not exist in the database are silently skipped
"""

import logging
import hashlib

import httpx

from config import (
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
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


def _prop_value(schema_type: str, raw_value) -> dict | None:
    """Build a Notion property value object for a given schema type.

    Returns *real* None (not a dict with null) when there is no valid value,
    so the caller can omit the property entirely.
    """
    s = str(raw_value).strip() if raw_value is not None else ""
    is_empty = not s or s.upper() == "N/A"

    # ── text-ish types always send (even empty) ──
    if schema_type == "title":
        return {"title": [{"text": {"content": _safe_str(raw_value)}}]}
    if schema_type == "rich_text":
        return {"rich_text": [{"text": {"content": _safe_str(raw_value)}}]}

    # ── url: omit if empty ──
    if schema_type == "url":
        if is_empty:
            return None
        return {"url": s}

    # ── select: omit if empty ──
    if schema_type == "select":
        if is_empty:
            return None
        name = s.replace(",", " -")
        return {"select": {"name": name}}

    # ── number: omit if empty ──
    if schema_type == "number":
        if is_empty or raw_value is None:
            return None
        try:
            return {"number": int(raw_value)}
        except (ValueError, TypeError):
            try:
                return {"number": float(raw_value)}
            except (ValueError, TypeError):
                return None

    # ── date: omit if empty ──
    if schema_type == "date":
        if is_empty:
            return None
        return {"date": {"start": s}}

    # ── fallback ──
    logger.debug(f"Unhandled schema type '{schema_type}', using rich_text")
    return {"rich_text": [{"text": {"content": _safe_str(raw_value)}}]}


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
        self.db_schema: dict[str, str] = {}         # property-name → type
        self.title_column: str = "Institution"       # will be detected

    # ── Database validation & schema loading ──────────────────────────

    async def validate_database(self, client: httpx.AsyncClient):
        """Fetch database metadata and populate self.db_schema."""
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

        # database title
        db_title = "".join(
            t.get("plain_text", "") for t in (db.get("title") or [])
        )
        logger.info(f"Database title: {db_title}")
        logger.info(f"Database properties ({len(props)}):")

        self.db_schema.clear()
        for name, schema in props.items():
            ptype = schema.get("type", "rich_text")
            self.db_schema[name] = ptype
            logger.info(f"  {name}: {ptype}")
            if ptype == "title":
                self.title_column = name

        return True

    # ── Existing page loading ─────────────────────────────────────────

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

                    # extract title text
                    title_obj = page_props.get(self.title_column, {})
                    title_text = _extract_text(title_obj, self.db_schema.get(self.title_column, "title"))

                    # extract program text (try several known columns)
                    prog_text = ""
                    for col in ("Program", "program", "Name"):
                        if col in page_props:
                            prog_text = _extract_text(page_props[col], self.db_schema.get(col, "rich_text"))
                            if prog_text:
                                break

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

    # ── Properties builder (schema-aware) ─────────────────────────────

    def _build_properties(self, record: dict) -> dict:
        """Build a properties dict that exactly matches the live database schema."""
        props: dict = {}

        for notion_name, schema_type in self.db_schema.items():
            # Find the agent field that corresponds to this Notion column
            agent_key = _agent_field(notion_name)

            # Handle special cases that need different lookup logic
            if notion_name == self.title_column:
                raw_value = record.get("institution", record.get("institution", ""))
            elif notion_name == "School":
                raw_value = record.get("school") or record.get("institution", "")
            elif notion_name == "Due Date":
                raw_value = record.get("due_date", "")
            elif agent_key == "importance":
                raw_value = record.get("importance", 5)
            elif agent_key == "days_to_prepare":
                raw_value = record.get("days_to_prepare", 0)
            else:
                raw_value = record.get(agent_key, "")

            # Build the structured value
            value = _prop_value(schema_type, raw_value)
            if value is not None:
                props[notion_name] = value

        return props

    # ── Upsert ────────────────────────────────────────────────────────

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

    # ── Sync all ──────────────────────────────────────────────────────

    async def sync_all(self, records: list[dict]):
        if not records:
            return 0, 0
        logger.info(
            f"Syncing {len(records)} records to database: {self.db_id[:8]}..."
        )
        created, updated = 0, 0
        async with httpx.AsyncClient(headers=_headers(), timeout=30) as client:
            # 1) Validate database access + load schema
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


# ── Utility ───────────────────────────────────────────────────────────

def _extract_text(prop_obj: dict, prop_type: str) -> str:
    """Extract plain text from a Notion property or plain rich-text array."""
    if not prop_obj:
        return ""
    # Handle list format (array of {plain_text, ...})
    if isinstance(prop_obj, list):
        return "".join(t.get("plain_text", "") for t in prop_obj)
    # Handle property wrapper format
    items = prop_obj.get(prop_type, [])
    return "".join(t.get("plain_text", "") for t in items)
