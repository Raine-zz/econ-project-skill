"""
Webpage fetcher — downloads HTML from seed URLs and follows on-domain links
up to MAX_DEPTH.  Uses httpx for async HTTP.

Self-healing URL discovery:
  - If a seed URL yields 0 relevant pages, automatically attempts URL discovery.
  - Discovered URLs are persisted to data/discovered_urls.json.
  - On the next run they replace the original seed URLs for those schools.
  - GitHub Actions cache carries discovered_urls.json across runs.
"""

import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import (
    REQUEST_TIMEOUT, MAX_DEPTH, MAX_PAGES_PER_SCHOOL,
    TARGET_KEYWORDS, SEED_URLS,
)
from utils.helper import is_target_program
from utils.url_discovery import discover_programme_urls

logger = logging.getLogger(__name__)

DISCOVERED_FILE = Path(__file__).resolve().parent.parent / "data" / "discovered_urls.json"


def _load_discovered_urls() -> dict[str, str]:
    """Load previously discovered URLs from disk. {school_name: url}."""
    if not DISCOVERED_FILE.exists():
        return {}
    try:
        data = json.loads(DISCOVERED_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, str) and v.startswith("http")}
    except Exception:
        logger.warning("Failed to load discovered_urls.json")
    return {}


def _save_discovered_urls(discovered: dict[str, str]):
    """Persist the current discovered URLs map to disk."""
    DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERED_FILE.write_text(
        json.dumps(discovered, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_effective_seeds(discovered: dict[str, str]) -> list[dict]:
    """
    Merge SEED_URLS with discovered URLs. Discovered take priority.
    """
    effective = []
    for seed in SEED_URLS:
        if seed["school"] in discovered:
            d_url = discovered[seed["school"]]
            if d_url != seed["url"]:
                logger.info(f"  Using discovered URL for {seed['school']}: {d_url}")
            effective.append({"school": seed["school"], "url": d_url})
        else:
            effective.append(seed)
    return effective


async def _fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} fetching {url}")
        return None
    except Exception:
        return None


def _extract_on_domain_links(base_url: str, html: str) -> list[str]:
    if not html:
        return []
    base_domain = urlparse(base_url).netloc
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if urlparse(href).netloc == base_domain:
            links.add(href)
    return list(links)


async def _crawl_from_seed(
    client: httpx.AsyncClient,
    seed_url: str,
    school_name: str,
) -> tuple[list[dict], set[str]]:
    visited: set[str] = set()
    pages: list[dict] = []
    queue: list[tuple[str, int]] = [(seed_url, 0)]

    while queue and len(pages) < MAX_PAGES_PER_SCHOOL:
        url, depth = queue.pop(0)
        if url in visited or depth > MAX_DEPTH:
            continue
        visited.add(url)

        html = await _fetch_page(client, url)
        if not html:
            continue

        if is_target_program(html, TARGET_KEYWORDS):
            pages.append({"url": url, "html": html})

        if depth < MAX_DEPTH:
            for link in _extract_on_domain_links(url, html):
                if link not in visited:
                    queue.append((link, depth + 1))

    return pages, visited


async def run_crawler() -> list[dict]:
    """
    Main entry: crawl all schools, with self-healing URL discovery.
    Returns [{school, url, html, source}, ...].
    """
    # ── Load persisted discovered URLs ──
    saved = _load_discovered_urls()
    effective_seeds = _build_effective_seeds(saved)

    results: list[dict] = []
    discovery_log: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "econ-project-skill/1.0 (academic-research)"},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        # ── Phase 1: crawl all (effective) seed URLs ──
        school_results: list[tuple[str, list[dict], str]] = []
        for seed in effective_seeds:
            pages, _visited = await _crawl_from_seed(
                client, seed["url"], seed["school"]
            )
            school_results.append((seed["school"], pages, seed["url"]))
            logger.info(f"  {seed['school']}: {len(pages)} pages")
            for page in pages:
                results.append({
                    "school": seed["school"],
                    "url": page["url"],
                    "html": page["html"],
                    "source": "discovered" if seed["school"] in saved else "seed",
                })

        # ── Phase 2: URL discovery for schools with 0 pages ──
        new_discoveries: dict[str, str] = {}
        for school_name, pages, seed_url in school_results:
            if pages:
                continue

            logger.info(
                f"  {school_name}: 0 relevant pages, discovering alternative URLs..."
            )
            discovered = await discover_programme_urls(
                client, seed_url, max_candidates=3
            )
            if not discovered:
                logger.warning(f"  {school_name}: URL discovery found nothing")
                continue

            for d in discovered:
                logger.info(f"    candidate (score={d['score']}): {d['url']}")

            best = discovered[0]
            disc_pages, _disc_visited = await _crawl_from_seed(
                client, best["url"], school_name
            )
            logger.info(f"  {school_name}: {len(disc_pages)} pages from discovered URL")

            for page in disc_pages:
                results.append({
                    "school": school_name,
                    "url": page["url"],
                    "html": page["html"],
                    "source": "discovered",
                })

            # Auto-accept if score >= 15 (very confident match)
            if best["score"] >= 15 and disc_pages:
                new_discoveries[school_name] = best["url"]

            discovery_log.append({
                "school": school_name,
                "old_url": seed_url,
                "candidates": [
                    {"url": d["url"], "score": d["score"], "source": d.get("source", "")}
                    for d in discovered
                ],
            })

    # ── Auto-persist high-confidence discoveries ──
    if new_discoveries:
        merged = {**saved, **new_discoveries}
        _save_discovered_urls(merged)
        logger.info(
            f"Auto-saved {len(new_discoveries)} discovered URLs to discovered_urls.json"
        )
        for name, url in new_discoveries.items():
            logger.info(f"  {name} → {url}")

    # ── Print discovery summary ──
    if discovery_log:
        logger.info("=== URL Discovery Summary ===")
        for entry in discovery_log:
            logger.info(f"  {entry['school']}: old={entry['old_url']}")
            for c in entry["candidates"]:
                tag = " (auto-accepted)" if entry["school"] in new_discoveries else ""
                logger.info(f"    → score={c['score']}  {c['url']}{tag}")

    return results
