"""
Webpage fetcher — downloads HTML from seed URLs and follows on-domain links
up to MAX_DEPTH.  Uses httpx for async HTTP.

When a seed URL fails (404/403) or yields zero relevant pages, the fetcher
automatically attempts URL discovery to find the correct programme page.
"""

import asyncio
import logging
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


async def _fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a single page, return HTML text or None on failure."""
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
    """Return absolute URLs that share the same domain as base_url."""
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
    """
    BFS crawl from a given URL. Returns (pages, visited_urls).
    """
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
            logger.debug(f"  kept: {url}")

        if depth < MAX_DEPTH:
            for link in _extract_on_domain_links(url, html):
                if link not in visited:
                    queue.append((link, depth + 1))

    return pages, visited


async def run_crawler() -> list[dict]:
    """
    Main entry: crawl all SEED_URLS concurrently.
    Returns [{school, url, html}, ...].
    """
    results: list[dict] = []
    discovery_log: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "econ-project-skill/1.0 (academic-research)"},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        # ── Phase 1: crawl all seed URLs ──
        school_results: list[tuple[str, list[dict]]] = []
        for seed in SEED_URLS:
            pages, _visited = await _crawl_from_seed(
                client, seed["url"], seed["school"]
            )
            school_results.append((seed["school"], pages, seed["url"]))
            logger.info(
                f"  {seed['school']}: {len(pages)} pages from seed URL"
            )
            for page in pages:
                results.append({
                    "school": seed["school"],
                    "url": page["url"],
                    "html": page["html"],
                    "source": "seed",
                })

        # ── Phase 2: URL discovery for schools with 0 pages ──
        for school_name, pages, seed_url in school_results:
            if pages:
                continue  # already got results

            logger.info(
                f"  {school_name}: seed URL returned 0 relevant pages, "
                f"attempting URL discovery..."
            )

            discovered = await discover_programme_urls(
                client, seed_url, max_candidates=3
            )

            if not discovered:
                logger.warning(f"  {school_name}: URL discovery found nothing")
                continue

            for d in discovered:
                logger.info(
                    f"    discovered candidate (score={d['score']}): {d['url']}"
                )

            # Try the best candidate
            best = discovered[0]
            disc_pages, _disc_visited = await _crawl_from_seed(
                client, best["url"], school_name
            )
            logger.info(
                f"  {school_name}: {len(disc_pages)} pages from discovered URL"
            )

            for page in disc_pages:
                results.append({
                    "school": school_name,
                    "url": page["url"],
                    "html": page["html"],
                    "source": "discovered",
                })

            # Log all candidates for manual review
            discovery_log.append({
                "school": school_name,
                "old_url": seed_url,
                "candidates": [
                    {"url": d["url"], "score": d["score"], "source": d.get("source", "")}
                    for d in discovered
                ],
            })

    # ── Print discovery summary ──
    if discovery_log:
        logger.info("=== URL Discovery Summary (consider updating config.py) ===")
        for entry in discovery_log:
            logger.info(f"  {entry['school']}:")
            logger.info(f"    old: {entry['old_url']}")
            for c in entry["candidates"]:
                logger.info(f"    → score={c['score']}  {c['url']}")

    return results
