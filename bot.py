#!/usr/bin/env python3
"""
Slack Bot — natural-language assistant for the Econ Project Skill.

Usage:
  export DEEPSEEK_API_KEY="sk-..."
  export SLACK_BOT_TOKEN="xoxb-..."
  export SLACK_APP_TOKEN="xapp-..."
  export NOTION_TOKEN="..."
  export NOTION_DATABASE_ID="..."

  python bot.py

The bot connects via Socket Mode (no public URL needed).
It answers @mention questions by calling DeepSeek function-calling,
then executing the appropriate tool (query Notion, generate PDF, etc.)
"""

import asyncio
import logging
import sys

from config import (
    SLACK_BOT_TOKEN,
    SLACK_APP_TOKEN,
    NOTION_TOKEN,
    NOTION_DATABASE_ID,
    LOG_LEVEL,
)
from utils.notion_helper import NotionSync
from utils.slack_bot import SlackBot

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("slack-bot")


def main():
    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.error("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set")
        sys.exit(1)

    # Connect to Notion (only needed for query/report tools)
    notion = None
    if NOTION_TOKEN and NOTION_DATABASE_ID:
        notion = NotionSync()
        logger.info("Notion connected")

    bot = SlackBot(
        bot_token=SLACK_BOT_TOKEN,
        app_token=SLACK_APP_TOKEN,
        notion_client=notion,
    )

    logger.info("Starting Slack Bot...")
    asyncio.run(bot.start())


if __name__ == "__main__":
    main()
