"""
URL Discovery — when a seed URL returns 404/403 or yields no relevant pages,
attempt to find the correct economics/finance graduate programs page.

Strategy (in order):
  1. Try common path patterns on the same domain
  2. Fetch institution homepage, extract on-domain links
  3. Score links by keyword relevance, return top candidates
"""

import logging
import re
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from config import TARGET_KEYWORDS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Path patterns to try when the seed URL fails
CANDIDATE_PATHS = [
    "/graduate",
    "/graduate/programmes",
    "/graduate/programs",
    "/postgraduate",
    "/masters",
    "/master",
    "/msc",
    "/mphil",
    "/phd",
    "/programs",
    "/programmes",
    "/study/graduate",
    "/studies/graduate",
    "/study/postgraduate",
    "/admissions/graduate",
    "/education/graduate",
    "/economics/graduate",
    "/economics/postgraduate",
    "/economics/masters",
    "/economics/msc",
    "/economics/phd",
    "/economics/study",
]


# Scoring weights for link keywords (higher = more likely correct)
LINK_SCORE = {
    "master": 10,
    "msc": 10,
    "mphil": 8,
    "mres": 8,
    "phd": 5,
    "dphil": 5,
    "doctor": 5,
    "graduate": 8,
    "postgraduate": 8,
    "economics": 5,
    "econometrics": 5,
    "finance": 5,
    "program": 3,
    "programme": 3,
    "admission": 3,
    "apply": 3,
    "application": 3,
    "study": 2,
    "course": 2,
    "degree": 2,
    "requirement": 2,
}


async def discover_programme_urls(
    client: httpx.AsyncClient,
    seed_url: str,
    max_candidates: int = 3,
) -> list[dict]:
    """
    Try to find the correct economics/finance graduate programme page.
    Returns list of {url, score, source} dicts sorted by score desc.
    """
    base_domain = _domain_base(seed_url)
    candidates: list[dict] = []

    # ── Step 1: try common path patterns ──
    pattern_results = await _try_patterns(client, base_domain)
    candidates.extend(pattern_results)

    # ── Step 2: if still no good hits, scrape homepage ──
    if not _has_good_hit(candidates):
        homepage_results = await _scrape_homepage(client, base_domain)
        candidates.extend(homepage_results)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for c in sorted(candidates, key=lambda x: x["score"], reverse=True):
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)

    return unique[:max_candidates]


def _domain_base(url: str) -> str:
    """Return scheme + netloc (no path), e.g. https://www.lse.ac.uk"""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _has_good_hit(candidates: list[dict], threshold: int = 8) -> bool:
    return any(c.get("score", 0) >= threshold for c in candidates)


async def _try_patterns(
    client: httpx.AsyncClient, domain: str
) -> list[dict]:
    """Try known candidate paths against the domain."""
    results: list[dict] = []
    for path in CANDIDATE_PATHS:
        url = urljoin(domain, path)
        if await _is_accessible(client, url):
            score = _score_url(url)
            results.append({"url": url, "score": score, "source": "pattern"})
    return results


async def _scrape_homepage(
    client: httpx.AsyncClient, domain: str
) -> list[dict]:
    """Fetch the domain homepage, extract links, score them."""
    results: list[dict] = []
    page_urls = [domain, f"{domain}/en", f"{domain}/economics"]

    for page_url in page_urls:
        html = await _fetch_text(client, page_url)
        if not html:
            continue

        links = _extract_on_domain_links(page_url, html)
        for link in links:
            score = _score_url(link)
            if score >= 4:  # minimum relevance threshold
                results.append({"url": link, "score": score, "source": "homepage"})

    return results


async def _is_accessible(client: httpx.AsyncClient, url: str) -> bool:
    """Check if URL returns 2xx."""
    try:
        resp = await client.head(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        return 200 <= resp.status_code < 300
    except Exception:
        return False


async def _fetch_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch page HTML, return None on failure."""
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _extract_on_domain_links(base_url: str, html: str) -> list[str]:
    """Return absolute URLs that share the same domain as base_url."""
    base_domain = urlparse(base_url).netloc
    links: set[str] = set()
    for a in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = a.group(1)
        # skip anchors, javascript, mailto
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc == base_domain:
            links.add(full)
    return list(links)


def _score_url(url: str) -> int:
    """Score a URL by how likely it points to an economics graduate programme."""
    lower = url.lower()
    score = 0
    for keyword, weight in LINK_SCORE.items():
        if keyword in lower:
            score += weight
    # Penalize very long URLs, anchors, PDFs
    if lower.endswith((".pdf", ".docx", ".jpg", ".png")):
        score = 0
    if "#" in lower:
        score -= 2
    if "?" in lower and len(lower.split("?")[-1]) > 20:
        score -= 2
    return max(0, score)
