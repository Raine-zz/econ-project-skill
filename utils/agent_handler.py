"""
Agent handler — sends scraped HTML + prompt to DeepSeek API, parses the
structured JSON response.
"""

import json
import logging
from pathlib import Path

import httpx

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, AGENT_MODEL

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "econ_project_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


async def analyse_page(client: httpx.AsyncClient, html: str) -> list[dict]:
    """
    Send a single page to the agent model; return parsed programme records.
    Truncate HTML to avoid token limits.
    """
    truncated = html[:30_000]  # rough token cap
    user_message = f"Analyse the following webpage HTML and extract programmes:\n\n{truncated}"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": AGENT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.0,
    }

    try:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        return _parse_json(raw)
    except Exception:
        logger.exception("Agent call failed")
        return []


def _parse_json(raw: str) -> list[dict]:
    """Extract JSON array from model response (may be wrapped in markdown fences)."""
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        result = json.loads(raw.strip())
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        logger.warning("Failed to parse agent JSON response")
    return []


async def run_agent(pages: list[dict]) -> list[dict]:
    """
    Process all scraped pages through the agent.
    Returns a flat list of all extracted programme records.
    """
    all_records: list[dict] = []
    async with httpx.AsyncClient() as client:
        for page in pages:
            records = await analyse_page(client, page["html"])
            for rec in records:
                rec["_source_url"] = page["url"]
                rec["_school"] = page.get("school", "")
            all_records.extend(records)
    logger.info(f"Agent extracted {len(all_records)} records from {len(pages)} pages")
    return all_records
