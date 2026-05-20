# Econ Project Skill

Automated skill that crawls official websites of top global Economics &
Finance programmes, extracts structured information via an AI agent,
syncs results to a Notion database, and sends a weekly summary to Slack.

## Features

- **Intelligent Crawling** — Visits seed URLs, follows on-domain links
  up to depth 2, keeps only pages mentioning Economics / Finance.
- **AI-Powered Analysis** — Uses a DeepSeek-compatible LLM to read
  programme pages and extract 30+ structured fields per programme.
- **Notion Sync** — Creates or updates pages in a Notion database.
  Supports filtering, sorting, tags, and calendar views.
- **Slack Digest** — Sends a weekly Markdown summary with high-priority
  items highlighted at the top.
- **Fully Automated** — Runs on GitHub Actions every Monday at 08:00 UTC
  (or manually via `workflow_dispatch`).

## Coverage

| Region | Institutions |
|--------|-------------|
| UK | LSE, Oxford, Cambridge |
| Europe | Toulouse SE, PSE, Bocconi, Bonn, Mannheim, SSE, Tinbergen, Tilburg, KU Leuven, Zurich, ETHZ, Sciences Po, Erasmus, Copenhagen |
| Hong Kong & Singapore | HKU, CUHK, HKUST, NUS, NTU |
| US Top-30 | Harvard, MIT, Stanford, UC Berkeley, Chicago, Princeton, Yale, Columbia, NYU, Northwestern, UPenn, UCLA, Duke, Michigan, Wisconsin |

## Project Structure

```
econ-project-skill/
├── main.py                  # Pipeline orchestrator
├── config.py                # School list, URLs, field mappings (no secrets)
├── requirements.txt
├── utils/
│   ├── fetcher.py           # Async web crawler (httpx + BeautifulSoup)
│   ├── agent_handler.py     # DeepSeek API integration
│   ├── notion_helper.py     # Notion database upsert
│   ├── slack_notifier.py    # Slack webhook summary
│   └── helper.py            # Date parsing, importance scoring
├── prompts/
│   └── econ_project_prompt.txt   # Agent system prompt
├── logs/                    # Runtime logs (git-ignored)
├── data/                    # Debug output (git-ignored)
├── .github/workflows/
│   └── weekly-sync.yml      # GitHub Actions cron job
└── README.md
```

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/econ-project-skill.git
cd econ-project-skill
```

### 2. Set up GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Description |
|-------------|-------------|
| `DEEPSEEK_API_KEY` | Your DeepSeek API key |
| `NOTION_TOKEN` | Notion internal integration token |
| `NOTION_DATABASE_ID` | Target Notion database ID (32-char hex) |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL |

### 3. Notion Database Setup

1. Create a **Notion Integration** at https://www.notion.so/my-integrations
2. Copy the *Internal Integration Secret* (this is `NOTION_TOKEN`)
3. Create a new database in Notion with the following properties:

| Property Name | Type |
|---------------|------|
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

4. Share the database with your integration (click "Connect to" in the DB).
5. Copy the database ID from the URL (32 characters) — this is `NOTION_DATABASE_ID`.

### 4. Run locally (optional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DEEPSEEK_API_KEY="sk-..."
export NOTION_TOKEN="secret_..."
export NOTION_DATABASE_ID="..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python main.py
```

## Customisation

- **Add more schools**: edit `PRIORITY_SCHOOLS` and `SEED_URLS` in `config.py`
- **Change keywords**: edit `TARGET_KEYWORDS` in `config.py`
- **Adjust importance scoring**: edit `compute_importance()` in `utils/helper.py`
- **Change LLM model**: set `AGENT_MODEL` env var (default: `deepseek-chat`)
- **Change schedule**: edit the `cron` line in `.github/workflows/weekly-sync.yml`

## License

MIT
