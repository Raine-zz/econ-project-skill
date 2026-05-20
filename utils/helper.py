from datetime import datetime, date, timedelta
import re
from typing import Optional

# ---------------------------------------------------------------------------
#  DATE UTILITIES
# ---------------------------------------------------------------------------

def parse_due_date(text: str) -> Optional[date]:
    """Attempt to parse a human deadline string into a date object."""
    if not text or text.strip().upper() == "N/A":
        return None

    patterns = [
        (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", None),          # 2026-01-15
        (r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})", "%d %b %Y"),
        (r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s+(\d{4})", "%b %d %Y"),
    ]

    for pattern, fmt in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            if fmt:
                dt = datetime.strptime(m.group(0), fmt)
                return dt.date()
            else:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def days_until(target: Optional[date]) -> Optional[int]:
    """Return days from today until target date (can be negative)."""
    if target is None:
        return None
    return (target - date.today()).days


# ---------------------------------------------------------------------------
#  IMPORTANCE SCORING ENGINE
# ---------------------------------------------------------------------------

def compute_importance(
    page_text: str,
    due_date_text: Optional[str] = None,
    base_score: int = 5,
) -> int:
    """Compute importance (1-10) from page content heuristics."""
    score = base_score
    text_lower = page_text.lower() if page_text else ""

    # Funding / scholarship
    funding_keywords = ["scholarship", "fellowship", "stipend", "funding", "tuition waiver",
                        "fully funded", "financial aid", "studentship", "sponsor"]
    if any(kw in text_lower for kw in funding_keywords):
        score += 2

    # Strong placement / PhD-track hints
    placement_keywords = ["placement", "phd track", "doctoral track", "top placements",
                          "academic placement", "phd preparation"]
    if any(kw in text_lower for kw in placement_keywords):
        score += 1

    # Deadline urgency
    parsed = parse_due_date(due_date_text or "")
    if parsed:
        remaining = days_until(parsed)
        if remaining is not None and 0 < remaining <= 60:
            score += 1

    # Penalty: marginal fit
    generic_keywords = ["management only", "mba", "executive education", "professional development"]
    if any(kw in text_lower for kw in generic_keywords):
        score -= 1

    return max(1, min(10, score))


def is_target_program(text: str, keywords: list[str]) -> bool:
    """Quick keyword check before invoking the agent."""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)
