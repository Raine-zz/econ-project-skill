# Econ Project Skill

Automated skill that crawls official websites of top global Economics &
Finance programmes, extracts structured information via an AI agent,
syncs results to a Notion database, and sends a weekly summary to Slack.

## Features

- **Intelligent Crawling** — Visits seed URLs, follows on-domain links
  up to depth 2, keeps only pages mentioning Economics / Finance.
- **Self-healing URLs** — When a seed URL returns 404/403, automatically
  discovers the correct programme page and persists it across runs.
- **AI-Powered Analysis** — Uses a DeepSeek-compatible LLM to read
  programme pages and extract 30+ structured fields per programme.
- **Notion Sync** — Schema-aware upsert into a Notion database.
  Supports filtering, sorting, tags, and calendar views.
- **Slack Digest** — Sends a weekly Markdown summary with high-priority
  items highlighted at the top.
- **Slack Chat Bot** — Natural language assistant via `@bot`. Ask about
  programmes, get stats, generate PDF reports, or trigger re-crawls.
- **GitHub Actions** — Runs weekly every Monday at 08:00 UTC
  (or manually via `workflow_dispatch`).

---

## Coverage

| Region | Institutions |
|--------|-------------|
| UK | LSE, Oxford, Cambridge |
| Europe | Toulouse SE, PSE, Bocconi, Bonn, Mannheim, SSE, Tinbergen, Tilburg, KU Leuven, Zurich, ETHZ, Sciences Po, Erasmus, Copenhagen, CEMFI, EIEF, Barcelona SE, UCLouvain, HEC Paris, HEC Lausanne, CEU, Oslo, Aarhus |
| Hong Kong & Singapore | HKU, CUHK, HKUST, NUS, NTU |
| US Top-30 | Harvard, MIT, Stanford, UC Berkeley, Chicago, Princeton, Yale, Columbia, NYU, Northwestern, UPenn, UCLA, Duke, Michigan, Wisconsin |

---

## Project Structure

```
econ-project-skill/
├── main.py                    # Pipeline orchestrator (fetch → agent → notion → slack)
├── bot.py                     # Slack Bot entry point (Socket Mode)
├── start.sh                   # One-command launcher for the Slack Bot
├── config.py                  # School list, URLs, field mappings (no secrets)
├── requirements.txt
├── .env.example               # Template for local environment variables
├── utils/
│   ├── fetcher.py             # Async web crawler + URL self-healing
│   ├── url_discovery.py       # Auto-discover correct URLs when seeds break
│   ├── agent_handler.py       # DeepSeek API integration
│   ├── notion_helper.py       # Notion database upsert + query (schema-aware)
│   ├── slack_notifier.py      # Weekly Slack webhook summary
│   ├── slack_bot.py           # Slack Bot: LLM function calling → tools
│   ├── pdf_report.py          # PDF generation (fpdf2)
│   └── helper.py              # Date parsing, importance scoring
├── prompts/
│   ├── econ_project_prompt.txt  # Agent system prompt
│   └── slack_bot_prompt.txt     # Bot system prompt
├── .github/workflows/
│   └── weekly-sync.yml        # GitHub Actions cron + manual trigger
├── .gitignore
└── README.md
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/econ-project-skill.git
cd econ-project-skill
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment variables

Copy `.env.example` to `.env` and fill in your tokens (never commit `.env`):

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `NOTION_TOKEN` | Notion internal integration secret |
| `NOTION_DATABASE_ID` | Notion database ID (32-char hex) |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook (for weekly summary) |
| `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token `xoxb-...` (for chat) |
| `SLACK_APP_TOKEN` | Slack App-Level Token `xapp-...` (for Socket Mode) |

### 4. GitHub Actions (weekly automation)

Go to your repo **Settings → Secrets and variables → Actions** and add the
same variables listed above as **Repository Secrets**.

### 5. Notion Database Setup

1. Create a **Notion Integration** at https://www.notion.so/my-integrations
2. Copy the *Internal Integration Secret* → `NOTION_TOKEN`
3. Create a database with these properties:

| Property | Type |
|----------|------|
| Institution | Title |
| Program | Rich Text |
| Website | URL |
| Requirement | Rich Text |
| Project Link | URL |
| Region | Select |
| Country | Select |
| City | Rich Text |
| Degree Type | Select |
| Orientation | Select |
| Preference | Rich Text |
| Process | Select |
| Due Date | Date |
| Days to Prepare | Number |
| Admission | Select |
| Study Period | Rich Text |
| Tuition | Rich Text |
| Language | Select |
| IELTS | Rich Text |
| GRE | Select |
| GPA | Rich Text |
| CV | Select |
| Core Requirements | Rich Text |
| Field | Select |
| Notes | Rich Text |
| Interview | Select |
| Summary | Rich Text |
| Importance | Number |
| School | Select |

4. Connect the integration: `...` → Connections → your integration
5. Copy the database ID from the URL → `NOTION_DATABASE_ID`

### 6. Slack App Setup (for the chat bot)

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Enter a name and pick your workspace
3. **Socket Mode** → toggle ON → generate `xapp-...` token → `SLACK_APP_TOKEN`
4. **OAuth & Permissions** → add scopes: `chat:write`, `files:write`, `app_mentions:read`
5. **Install to Workspace** → copy `xoxb-...` token → `SLACK_BOT_TOKEN`
6. **Event Subscriptions** → ON → subscribe to `app_mention` event
7. Invite the bot to a channel: `/invite @your-bot-name`

---

## Usage

### One-time pipeline

```bash
source .env && python3 main.py
```

### Slack Chat Bot

```bash
./start.sh
```

Then in a Slack channel where the bot is invited:

```
@bot 查 LSE 经济硕士
@bot 高优先级项目
@bot 截止日在30天内的
@bot 发一份 PDF 报告
@bot 重新抓取
```

---

## Customisation

- **Add schools**: edit `PRIORITY_SCHOOLS` and `SEED_URLS` in `config.py`
- **Change keywords**: edit `TARGET_KEYWORDS` in `config.py`
- **Adjust importance scoring**: edit `compute_importance()` in `utils/helper.py`
- **Change LLM model**: set `AGENT_MODEL` env var (default: `deepseek-chat`)
- **Change schedule**: edit the `cron` line in `.github/workflows/weekly-sync.yml`

---

## License

MIT
