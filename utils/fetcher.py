"""
Webpage fetcher — downloads HTML from seed URLs and follows on-domain links
up to MAX_DEPTH.  Uses httpx for async HTTP.
"""

import asyncio
from urllib.parse import urljoin, urlparse
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import (
    REQUEST_TIMEOUT, MAX_DEPTH, MAX_PAGES_PER_SCHOOL,
    TARGET_KEYWORDS, SEED_URLS,
)
from utils.helper import is_target_program


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a single page, return HTML text or None on failure."""
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def extract_on_domain_links(base_url: str, html: str) -> list[str]:
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


async def crawl_school(client: httpx.AsyncClient, seed: dict) -> list[dict]:
    """
    BFS crawl starting from seed["url"], limited by MAX_DEPTH and
    MAX_PAGES_PER_SCHOOL.  Returns a list of {url, html} dicts.
    """
    visited: set[str] = set()
    pages: list[dict] = []
    queue: list[tuple[str, int]] = [(seed["url"], 0)]

    while queue and len(pages) < MAX_PAGES_PER_SCHOOL:
        url, depth = queue.pop(0)
        if url in visited or depth > MAX_DEPTH:
            continue
        visited.add(url)

        html = await fetch_page(client, url)
        if not html:
            continue

        # Quick keyword gate — if the page mentions econ/finance, keep it
        if is_target_program(html, TARGET_KEYWORDS):
            pages.append({"url": url, "html": html})

        if depth < MAX_DEPTH:
            for link in extract_on_domain_links(url, html):
                if link not in visited:
                    queue.append((link, depth + 1))

    return pages


async def run_crawler() -> list[dict]:
    """
    Main entry: crawl all SEED_URLS concurrently.
    Returns [{school, url, html}, ...].
    """
    results: list[dict] = []
    async with httpx.AsyncClient(
        headers={"User-Agent": "econ-project-skill/1.0 (academic-research)"},
        timeout=REQUEST_TIMEOUT,
    ) as client:
        tasks = [crawl_school(client, s) for s in SEED_URLS]
        school_results = await asyncio.gather(*tasks)

    for seed, pages in zip(SEED_URLS, school_results):
        for page in pages:
            results.append({
                "school": seed["school"],
                "url": page["url"],
                "html": page["html"],
            })
    return results
