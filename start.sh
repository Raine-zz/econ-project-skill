#!/usr/bin/env bash
# Start the Econ Project Skill Slack Bot.
# Requires .env file in the same directory with:
#   SLACK_BOT_TOKEN, SLACK_APP_TOKEN, DEEPSEEK_API_KEY,
#   NOTION_TOKEN, NOTION_DATABASE_ID
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Error: .env file not found. Create one with your tokens."
    exit 1
fi

echo "Loading environment..."
set -a && source .env && set +a

echo "Starting Econ Slack Bot..."
python3 bot.py
