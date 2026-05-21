"""
Slack Bot core — receives messages via Socket Mode, uses DeepSeek function
calling to pick the right tool, executes it, and replies to the channel.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import httpx
from slack_sdk.socket_mode.async_client import AsyncSocketModeClient
from slack_sdk.web.async_client import AsyncWebClient

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, AGENT_MODEL

logger = logging.getLogger(__name__)

# Tool definitions sent to DeepSeek
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_programs",
            "description": "Search tracked economics/finance programmes. Use when the user asks about specific schools, countries, regions, degree types, deadlines, or keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string", "description": "School name (partial match)"},
                    "country": {"type": "string"},
                    "region": {"type": "string", "enum": ["Europe", "Asia", "North America", "Oceania"]},
                    "degree_type": {"type": "string", "enum": ["MSc", "MA", "MPhil", "MRes", "PhD", "DPhil", "Direct PhD", "Joint/Dual Degree"]},
                    "importance_min": {"type": "integer", "minimum": 1, "maximum": 10},
                    "deadline_before": {"type": "string", "description": "YYYY-MM-DD format"},
                    "keyword": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Get aggregate statistics: total programmes, breakdown by region, country, degree type.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report",
            "description": "Generate and upload a PDF report of programmes matching the given filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "institution": {"type": "string"},
                    "country": {"type": "string"},
                    "region": {"type": "string"},
                    "importance_min": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_crawl",
            "description": "Re-crawl all school websites and update the database.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# Conversation context per channel (last 8 messages)
_CONVO: dict[str, list[dict]] = {}
MAX_CONVO = 8

SYSTEM_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "slack_bot_prompt.txt").read_text(encoding="utf-8")


class SlackBot:
    def __init__(self, bot_token: str, app_token: str, notion_client: "NotionSync" = None):
        self.web = AsyncWebClient(token=bot_token)
        self.socket = AsyncSocketModeClient(app_token=app_token, web_client=self.web)
        self.notion = notion_client
        self._httpx: Optional[httpx.AsyncClient] = None

    async def _get_httpx(self) -> httpx.AsyncClient:
        if self._httpx is None:
            self._httpx = httpx.AsyncClient(timeout=60)
        return self._httpx

    # ── Message handling ─────────────────────────────────────────────

    async def start(self):
        self.socket.socket_mode_request_listeners.append(self._on_message)
        await self.socket.connect()
        logger.info("Slack Bot connected (Socket Mode)")
        await self.socket._event_loop  # keep alive

    async def _on_message(self, client: AsyncSocketModeClient, req: dict):
        if req.get("type") != "events_api":
            return

        event = req.get("payload", {}).get("event", {})
        if event.get("type") != "app_mention":
            return

        channel = event.get("channel", "")
        user = event.get("user", "")
        text = event.get("text", "")
        thread_ts = event.get("ts", "")

        logger.info(f"@{user}: {text}")

        # Strip the @bot mention prefix
        clean_text = " ".join(text.split()[1:]) if text.startswith("<@") else text

        reply = await self._process(channel, clean_text)
        await self.web.chat_postMessage(
            channel=channel,
            text=reply,
            thread_ts=thread_ts,
            mrkdwn=True,
        )

    async def _process(self, channel: str, message: str) -> str:
        """Send message to LLM, handle tool calls, return Slack text."""

        if channel not in _CONVO:
            _CONVO[channel] = []
        convo = _CONVO[channel]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *convo[-MAX_CONVO:],
            {"role": "user", "content": message},
        ]

        try:
            client = await self._get_httpx()
            resp = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": AGENT_MODEL,
                    "messages": messages,
                    "tools": TOOLS,
                    "temperature": 0.0,
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception:
            logger.exception("LLM call failed")
            return ":x: 暂时无法处理，请稍后再试。"

        choice = result["choices"][0]
        msg = choice["message"]

        # Store conversation
        convo.append({"role": "user", "content": message})

        # If no tool call, return text directly
        if not msg.get("tool_calls"):
            reply = msg.get("content", "抱歉，我没有理解你的问题。")
            convo.append({"role": "assistant", "content": reply})
            return reply

        # Execute tool call(s)
        tool_call = msg["tool_calls"][0]
        fn_name = tool_call["function"]["name"]
        fn_args = json.loads(tool_call["function"].get("arguments", "{}"))

        logger.info(f"Tool call: {fn_name}({fn_args})")

        # Execute
        if fn_name == "query_programs":
            result_data = await self._query_programs(fn_args)
        elif fn_name == "get_stats":
            result_data = await self._get_stats()
        elif fn_name == "generate_report":
            result_data = await self._generate_report(channel, fn_args)
        elif fn_name == "trigger_crawl":
            result_data = await self._trigger_crawl()
        else:
            result_data = {"error": f"Unknown tool: {fn_name}"}

        # Send result back to LLM for final formatting
        tool_msg = {"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result_data, ensure_ascii=False)}

        try:
            resp2 = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": AGENT_MODEL,
                    "messages": messages + [msg, tool_msg],
                    "temperature": 0.0,
                },
                timeout=60,
            )
            resp2.raise_for_status()
            final = resp2.json()["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("LLM formatting call failed")
            final = self._format_raw(result_data)

        convo.append({"role": "assistant", "content": final})
        return final

    # ── Tool implementations ─────────────────────────────────────────

    async def _query_programs(self, args: dict) -> dict:
        """Query Notion database by filters."""
        if not self.notion:
            return {"error": "Notion not connected"}
        try:
            records = await self.notion.query(args)
            return {"count": len(records), "programmes": records[:15]}
        except Exception:
            logger.exception("query_programs failed")
            return {"error": "Query failed"}

    async def _get_stats(self) -> dict:
        if not self.notion:
            return {"error": "Notion not connected"}
        try:
            all_records = await self.notion.query({})
            by_region: dict[str, int] = {}
            by_degree: dict[str, int] = {}
            for r in all_records:
                region = r.get("region", "Unknown")
                degree = r.get("degree_type", "Unknown")
                by_region[region] = by_region.get(region, 0) + 1
                by_degree[degree] = by_degree.get(degree, 0) + 1
            return {
                "total": len(all_records),
                "by_region": by_region,
                "by_degree": by_degree,
            }
        except Exception:
            logger.exception("get_stats failed")
            return {"error": "Stats query failed"}

    async def _generate_report(self, channel: str, args: dict) -> dict:
        if not self.notion:
            return {"error": "Notion not connected"}
        try:
            from utils.pdf_report import generate_pdf
            records = await self.notion.query(args)
            pdf_path = generate_pdf(records)

            await self.web.files_upload(
                channels=channel,
                file=pdf_path,
                title="Econ_Programmes_Report.pdf",
            )
            return {"ok": True, "count": len(records), "message": f"PDF sent ({len(records)} programmes)"}
        except Exception:
            logger.exception("generate_report failed")
            return {"error": "Failed to generate PDF"}

    async def _trigger_crawl(self) -> dict:
        asyncio.create_task(self._run_crawl())
        return {"message": "爬虫已在后台启动，完成后会通知你。"}

    async def _run_crawl(self):
        from main import fetch_websites, agent_analyse, notion_sync
        pages = await fetch_websites()
        records = await agent_analyse(pages)
        if records:
            await notion_sync(records)

    def _format_raw(self, data: dict) -> str:
        """Fallback formatter when LLM formatting fails."""
        if "error" in data:
            return f":x: {data['error']}"

        if "count" in data and "programmes" in data:
            lines = [f"Found *{data['count']}* programmes:"]
            for p in data["programmes"][:10]:
                lines.append(
                    f"  • *{p.get('institution','?')}* — {p.get('program','?')} "
                    f"(imp={p.get('importance','?')})"
                )
            return "\n".join(lines)

        if "total" in data:
            return (
                f"Total: *{data['total']}* programmes\n"
                + "\n".join(f"  {r}: {c}" for r, c in data.get("by_region", {}).items())
            )

        return json.dumps(data, ensure_ascii=False, indent=2)
