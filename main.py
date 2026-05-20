# ============================================================================
# ECON PROJECT SKILL — Main Orchestrator
#
# Workflow:
#   1. fetch_websites()   — crawl seed URLs, return raw HTML pages
#   2. agent_analyse()    — send each page to DeepSeek, parse JSON records
#   3. notion_sync()      — upsert records into Notion database
#   4. slack_notify()     — send Markdown summary to Slack channel
#
# Designed to run headlessly inside GitHub Actions (weekly cron).
# ============================================================================

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Set up logging
# ---------------------------------------------------------------------------
from config import LOG_LEVEL

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("econ-skill")


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

async def fetch_websites():
    """Stage 1: crawl all seed URLs and collect relevant HTML pages."""
    from utils.fetcher import run_crawler
    logger.info("=== Stage 1: Fetching websites ===")
    pages = await run_crawler()
    logger.info(f"Fetched {len(pages)} relevant pages across all schools")

    # Save raw output for debugging / inspection
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / f"fetched_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(
        json.dumps([{"school": p["school"], "url": p["url"]} for p in pages],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return pages


async def agent_analyse(pages):
    """Stage 2: send pages to the agent, receive structured programme records."""
    if not pages:
        logger.warning("No pages to analyse — skipping agent stage")
        return []

    from utils.agent_handler import run_agent
    logger.info("=== Stage 2: Agent analysis ===")
    records = await run_agent(pages)
    logger.info(f"Agent returned {len(records)} programme records")

    # Save agent output
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(exist_ok=True)
    output_path = data_dir / f"records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


async def notion_sync(records):
    """Stage 3: upsert all records into Notion database."""
    if not records:
        logger.warning("No records to sync — skipping Notion stage")
        return {}

    import os
    if not os.getenv("NOTION_TOKEN") or not os.getenv("NOTION_DATABASE_ID"):
        logger.warning("NOTION_TOKEN or NOTION_DATABASE_ID not set — skipping Notion sync")
        return {"created": 0, "updated": 0}

    from utils.notion_helper import NotionSync
    logger.info("=== Stage 3: Notion sync ===")
    sync = NotionSync()
    created, updated = await sync.sync_all(records)
    logger.info(f"Notion sync complete: {created} created, {updated} updated")
    return {"created": created, "updated": updated}


async def slack_notify(records):
    """Stage 4: send weekly summary to Slack."""
    if not records:
        logger.warning("No records to summarise — skipping Slack stage")
        return False

    from utils.slack_notifier import send_slack_summary
    logger.info("=== Stage 4: Slack notification ===")
    sent = await send_slack_summary(records)
    if sent:
        logger.info("Slack summary sent successfully")
    else:
        logger.warning("Slack summary was not sent (check SLACK_WEBHOOK_URL)")
    return sent


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main():
    """Run the full pipeline sequentially."""
    start = datetime.now()
    logger.info("===== ECON PROJECT SKILL PIPELINE START =====")

    try:
        # 1. Fetch
        pages = await fetch_websites()

        # 2. Agent analyse
        records = await agent_analyse(pages)

        # 3. Notion sync
        if records:
            await notion_sync(records)

        # 4. Slack notify
        if records:
            await slack_notify(records)

    except Exception:
        logger.exception("Pipeline failed with unhandled exception")
        sys.exit(1)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"===== PIPELINE COMPLETE in {elapsed:.1f}s =====")


if __name__ == "__main__":
    asyncio.run(main())
