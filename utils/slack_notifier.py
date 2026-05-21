"""
Slack notifier — sends a weekly diff summary to Slack.
Only reports *changed* programmes (new, updated, removed).
Persists last week's state to data/last_week_records.json.
"""

import hashlib
import json
import logging
from datetime import date
from pathlib import Path

import httpx

from config import SLACK_WEBHOOK_URL, HIGH_IMPORTANCE_THRESHOLD

logger = logging.getLogger(__name__)

LAST_WEEK_FILE = Path(__file__).resolve().parent.parent / "data" / "last_week_records.json"


def _record_key(rec: dict) -> str:
    raw = f"{rec.get('institution','')}|{rec.get('program','')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_last_week() -> list[dict]:
    if not LAST_WEEK_FILE.exists():
        return []
    try:
        return json.loads(LAST_WEEK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_this_week(records: list[dict]):
    LAST_WEEK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_WEEK_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def diff_records(
    current: list[dict], previous: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (new_items, updated_items, removed_items)."""
    prev_map = {_record_key(r): r for r in previous}
    curr_map = {_record_key(r): r for r in current}

    new_items = [r for k, r in curr_map.items() if k not in prev_map]
    removed_items = [r for k, r in prev_map.items() if k not in curr_map]
    updated_items = []

    for k, curr_rec in curr_map.items():
        if k in prev_map:
            prev_rec = prev_map[k]
            # Check if any field changed
            relevant_fields = ["due_date", "importance", "notes", "process", "tuition", "admission"]
            changed = any(
                curr_rec.get(f) != prev_rec.get(f) for f in relevant_fields
            )
            if changed:
                updated_items.append(curr_rec)

    return new_items, updated_items, removed_items


def build_summary(records: list[dict]) -> str:
    """Build a diff-based Slack summary."""
    previous = _load_last_week()
    today_str = date.today().isoformat()

    if not previous:
        # First run — show all as new
        return _build_full_summary(records, today_str, first_run=True)

    new_items, updated_items, removed_items = diff_records(records, previous)
    change_count = len(new_items) + len(updated_items) + len(removed_items)

    if change_count == 0:
        return (
            f":white_check_mark: *Econ Project Weekly Report — {today_str}*\n"
            f"No changes. Total tracked: *{len(records)}* programmes."
        )

    lines = [
        f":mega: *Econ Project Weekly Report — {today_str}*",
        f"",
        f"Total tracked: *{len(records)}*  "
        f"(+{len(new_items)} new, {len(updated_items)} updated, {len(removed_items)} removed)",
        f"",
    ]

    # ── New ──
    if new_items:
        new_sorted = sorted(new_items, key=lambda r: r.get("importance", 0), reverse=True)
        lines.append(f":new: *NEW ({len(new_items)})*")
        for r in new_sorted[:10]:
            imp = r.get("importance", "?")
            due = r.get("due_date", "N/A")
            lines.append(
                f"  • *{r.get('institution','?')}* — {r.get('program','?')} (imp={imp})"
            )
            if due and due != "N/A":
                lines.append(f"    Deadline: {due}")
        if len(new_items) > 10:
            lines.append(f"  _... and {len(new_items) - 10} more_")
        lines.append("")

    # ── Updated ──
    if updated_items:
        upd_sorted = sorted(updated_items, key=lambda r: r.get("importance", 0), reverse=True)
        lines.append(f":arrows_counterclockwise: *UPDATED ({len(updated_items)})*")
        for r in upd_sorted[:10]:
            lines.append(
                f"  • *{r.get('institution','?')}* — {r.get('program','?')} "
                f"(due={r.get('due_date','N/A')}, imp={r.get('importance','?')})"
            )
        if len(updated_items) > 10:
            lines.append(f"  _... and {len(updated_items) - 10} more_")
        lines.append("")

    # ── Removed ──
    if removed_items:
        lines.append(f":x: *REMOVED ({len(removed_items)})*")
        for r in removed_items[:5]:
            lines.append(f"  • *{r.get('institution','?')}* — {r.get('program','?')}")
        if len(removed_items) > 5:
            lines.append(f"  _... and {len(removed_items) - 5} more_")
        lines.append("")

    # ── High priority snapshot ──
    high = [r for r in records if r.get("importance", 0) >= HIGH_IMPORTANCE_THRESHOLD]
    if high:
        lines.append(f"---")
        lines.append(f":rotating_light: *Current High Priority ({len(high)})*")
        for r in sorted(high, key=lambda r: r.get("importance", 0), reverse=True)[:5]:
            due = r.get("due_date", "N/A")
            lines.append(
                f"  • *{r.get('institution','?')}* — {r.get('program','?')} "
                f"(imp={r.get('importance','?')}, due={due})"
            )

    return "\n".join(lines)


def _build_full_summary(records: list[dict], today_str: str, first_run: bool = False) -> str:
    """Fallback: show all programmes (first run)."""
    sorted_records = sorted(records, key=lambda r: r.get("importance", 0), reverse=True)

    intro = ":tada: *First run!*" if first_run else ""
    lines = [
        f":mega: *Econ Project Weekly Report — {today_str}* {intro}",
        "",
        f"Total programmes tracked: *{len(records)}*",
        "",
    ]

    high = [r for r in sorted_records if r.get("importance", 0) >= HIGH_IMPORTANCE_THRESHOLD]
    if high:
        lines.append(f":rotating_light: *HIGH PRIORITY ({len(high)})*")
        for r in high[:8]:
            lines.append(
                f"  • *{r.get('institution','?')}* — {r.get('program','?')} "
                f"(imp={r.get('importance','?')})"
            )
        lines.append("")

    normal = [r for r in sorted_records if r.get("importance", 0) < HIGH_IMPORTANCE_THRESHOLD]
    if normal:
        lines.append(f":bookmark: *Other ({len(normal)})*")
        for r in normal[:10]:
            lines.append(
                f"  • *{r.get('institution','?')}* — {r.get('program','?')} "
                f"(imp={r.get('importance','?')})"
            )
        if len(normal) > 10:
            lines.append(f"  _... and {len(normal) - 10} more_")

    return "\n".join(lines)


async def send_slack_summary(records: list[dict]) -> bool:
    """Post the summary to Slack webhook, then save this week's state."""
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack notification")
        return False

    message = build_summary(records)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                SLACK_WEBHOOK_URL,
                json={"text": message, "mrkdwn": True},
                timeout=30,
            )
            resp.raise_for_status()
            logger.info("Slack summary sent successfully")

            # Persist this week's state for next diff
            save_this_week(records)
            return True
        except Exception:
            logger.exception("Failed to send Slack summary")
            return False
