"""
Notion helper — upsert (create or update) programme records into a Notion database
using the official notion-client.
"""

import logging
import hashlib
import json

from notion_client import Client

from config import NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_FIELD_MAP

logger = logging.getLogger(__name__)


def _make_key(record: dict) -> str:
    """Deterministic key from institution + program to avoid duplicates."""
    raw = f"{record.get('institution','')}|{record.get('program','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _safe_str(val, default="N/A") -> str:
    if val is None:
        return default
    return str(val)


class NotionSync:
    def __init__(self):
        self.client = Client(auth=NOTION_TOKEN)
        self.db_id = NOTION_DATABASE_ID
        self.existing_keys: dict[str, str] = {}  # key -> page_id
        self._load_existing()

    def _load_existing(self):
        """Fetch existing pages and build {key: page_id} dict."""
        try:
            cursor = None
            while True:
                resp = self.client.databases.query(
                    database_id=self.db_id,
                    start_cursor=cursor,
                    page_size=100,
                )
                for page in resp["results"]:
                    props = page.get("properties", {})
                    name_prop = props.get(NOTION_FIELD_MAP["Institution"], {})
                    title_text = ""
                    for t in name_prop.get("title", []):
                        title_text += t.get("plain_text", "")

                    prog_prop = props.get(NOTION_FIELD_MAP["Program"], {})
                    prog_text = ""
                    for t in prog_prop.get("rich_text", []):
                        prog_text += t.get("plain_text", "")

                    key = hashlib.md5(f"{title_text}|{prog_text}".encode()).hexdigest()
                    self.existing_keys[key] = page["id"]

                if not resp.get("has_more"):
                    break
                cursor = resp.get("next_cursor")
        except Exception:
            logger.exception("Failed to load existing Notion pages")

    def _build_properties(self, record: dict) -> dict:
        """Map a record dict to Notion page properties."""
        fm = NOTION_FIELD_MAP
        props = {}

        # Title field: Institution
        props[fm["Institution"]] = {
            "title": [{"text": {"content": _safe_str(record.get("institution"))}}]
        }

        # Rich text fields
        rich_fields = [
            fm["Program"], fm["Website"], fm["Requirement"], fm["Project Link"],
            fm["Region"], fm["Country"], fm["City"], fm["Degree Type"],
            fm["Orientation"], fm["Preference"], fm["Process"],
            fm["Application Deadline"], fm["Admission"], fm["Study Period"],
            fm["Tuition"], fm["Language"], fm["IELTS"],
            fm["GRE"], fm["GPA"], fm["CV"], fm["Core Requirements"],
            fm["Field"], fm["Notes"], fm["Interview"], fm["Summary"],
        ]
        for name in rich_fields:
            props[name] = {
                "rich_text": [{"text": {"content": _safe_str(record.get(name.lower().replace(" ", "_")))}}]
            }

        # Date field: Due Date
        due = record.get("due_date", "")
        if due and due != "N/A":
            props[fm["Due Date"]] = {"date": {"start": due}}
        else:
            props[fm["Due Date"]] = {"date": None}

        # Number field: Days to Prepare / Importance
        props[fm["Days to Prepare"]] = {
            "number": int(record.get("days_to_prepare", 0) or 0)
        }
        props[fm["Importance"]] = {
            "number": int(record.get("importance", 5) or 5)
        }

        # Select: School (optional — uses Institution as fallback)
        school_val = record.get("school", record.get("institution", ""))
        props["School"] = {"select": {"name": _safe_str(school_val)}}

        return props

    def upsert(self, record: dict):
        """Create or update a Notion page for the given record."""
        key = _make_key(record)
        properties = self._build_properties(record)

        try:
            if key in self.existing_keys:
                self.client.pages.update(
                    page_id=self.existing_keys[key],
                    properties=properties,
                )
                logger.debug(f"Updated: {record.get('program')}")
            else:
                resp = self.client.pages.create(
                    parent={"database_id": self.db_id},
                    properties=properties,
                )
                self.existing_keys[key] = resp["id"]
                logger.debug(f"Created: {record.get('program')}")
        except Exception:
            logger.exception(f"Notion upsert failed for {record.get('program')}")

    def sync_all(self, records: list[dict]):
        """Iterate all records and upsert each."""
        created, updated = 0, 0
        for rec in records:
            key = _make_key(rec)
            existed = key in self.existing_keys
            self.upsert(rec)
            if existed:
                updated += 1
            else:
                created += 1
        logger.info(f"Notion sync done: {created} created, {updated} updated")
        return created, updated
