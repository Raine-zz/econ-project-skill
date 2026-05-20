"""
Slack notifier — send a weekly summary to a Slack channel via Incoming Webhook.
"""

import json
import logging
from datetime import date

import httpx

from config import SLACK_WEBHOOK_URL, HIGH_IMPORTANCE_THRESHOLD

logger = logging.getLogger(__name__)


def build_summary(records: list[dict]) -> str:
    """
    Build a Markdown-formatted Slack message from extracted records.
    Orders by importance descending.
    """
    if not records:
        return ":white_check_mark: *Econ Project Skill Weekly Report* — No new or updated programmes this week."

    sorted_records = sorted(records, key=lambda r: r.get("importance", 0), reverse=True)

    blocks = [
        f":mega: *Econ Project Weekly Report — {date.today().isoformat()}*",
        f"",
        f"Total programmes tracked: *{len(records)}*",
        f"",
    ]

    high_priority = [r for r in sorted_records if r.get("importance", 0) >= HIGH_IMPORTANCE_THRESHOLD]

    if high_priority:
        blocks.append(":rotating_light: *HIGH PRIORITY ({})*".format(len(high_priority)))
        for r in high_priority:
            inst = r.get("institution", "N/A")
            prog = r.get("program", "N/A")
            imp = r.get("importance", "?")
            due = r.get("due_date", "N/A")
            web = r.get("website", "")
            blocks.append(
                f"  • *{inst}* — {prog}  (imp={imp})"
            )
            if due and due != "N/A":
                blocks.append(f"    Deadline: {due}")
            if web:
                blocks.append(f"    <{web}|Website>")
            summary = r.get("summary", "")
            if summary:
                blocks.append(f"    _{summary}_")
            blocks.append("")

    # Remaining
    normal = [r for r in sorted_records if r.get("importance", 0) < HIGH_IMPORTANCE_THRESHOLD]
    if normal:
        blocks.append("---")
        blocks.append(":bookmark: *Other Updates*")
        for r in normal:
            inst = r.get("institution", "N/A")
            prog = r.get("program", "N/A")
            imp = r.get("importance", "?")
            blocks.append(f"  • *{inst}* — {prog}  (imp={imp})")

    return "\n".join(blocks)


async def send_slack_summary(records: list[dict]) -> bool:
    """Post the summary to Slack webhook URL."""
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack notification")
        return False

    message = build_summary(records)
    payload = {
        "text": message,
        "mrkdwn": True,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(SLACK_WEBHOOK_URL, json=payload, timeout=30)
            resp.raise_for_status()
            logger.info("Slack summary sent successfully")
            return True
        except Exception:
            logger.exception("Failed to send Slack summary")
            return False
