"""Helpers for cleaning and decorating per-page titles.

Documentation sites typically suffix every <title> with the site name (e.g.
"1.1 Intro - khQuant Quantitative Trading Platform"). When we render every
page in a single PDF that suffix becomes useless visual noise on every entry.

The cleanup logic detects a *common trailing fragment* shared across most
page titles and strips it from each title. The detection is conservative: it
only kicks in when the suffix is non-trivial (>= 4 chars) and seen on the
majority of pages.

The optional ``add_column_title`` decoration prepends a section path inferred
from the heading hierarchy of each page. For "1.1 Intro" it produces
"1. <site_section> / 1.1 Intro" when a parent heading was discovered;
otherwise it falls back to the cleaned page title.
"""

from __future__ import annotations

import re

from app.document.models import ExtractedPage


_SEPARATORS = (" - ", " — ", " | ", " · ", " :: ", " — ")


def _common_trailing_fragment(titles: list[str]) -> str:
    """Find a non-trivial trailing fragment shared by most page titles.

    Returns the suffix string (including its leading separator) that should be
    stripped, or an empty string when no suitable suffix is found.
    """

    candidates: dict[str, int] = {}
    for title in titles:
        if not title:
            continue
        for sep in _SEPARATORS:
            idx = title.rfind(sep)
            if idx > 0:
                tail = title[idx:]
                if len(tail) - len(sep) >= 4:
                    candidates[tail] = candidates.get(tail, 0) + 1
    if not candidates:
        return ""
    # Pick the longest tail that appears on at least half of all titles.
    threshold = max(2, len(titles) // 2)
    best = ""
    for tail, count in candidates.items():
        if count >= threshold and len(tail) > len(best):
            best = tail
    return best


def strip_site_suffix(titles: list[str]) -> list[str]:
    """Remove a common trailing site-name suffix from each title."""

    suffix = _common_trailing_fragment(titles)
    if not suffix:
        return list(titles)
    cleaned: list[str] = []
    for title in titles:
        if title.endswith(suffix):
            cleaned.append(title[: -len(suffix)].rstrip())
        else:
            cleaned.append(title)
    return cleaned


_LEADING_NUMBER_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)(?:[\.\)、:：]\s*|\s+)")


def _leading_section_number(text: str) -> str:
    match = _LEADING_NUMBER_RE.match(text or "")
    if not match:
        return ""
    return match.group(1)


def column_path(page: ExtractedPage) -> str:
    """Infer a section path string for ``page`` from its title and headings.

    Examples:
        title="1.1 Intro" -> "1"
        title="2.3 Storage", headings ["2.3 Storage", ...] -> "2"
        title="API" (no leading number) -> ""

    The result is usable as a prefix; the caller decides separator/wrap.
    """

    number = _leading_section_number(page.title)
    if "." in number:
        return number.split(".", 1)[0]
    return number


def decorate_titles(
    pages: list[ExtractedPage],
    *,
    add_column_title: bool,
) -> None:
    """Mutate ``pages`` in-place: clean trailing site name and (optionally)
    prepend a column / section path.
    """

    cleaned = strip_site_suffix([p.title for p in pages])
    for page, new_title in zip(pages, cleaned):
        page.title = new_title

    if not add_column_title:
        return
    for page in pages:
        prefix = column_path(page)
        if not prefix:
            continue
        already_prefixed = page.title.startswith(f"{prefix}. ") and not page.title[
            len(prefix) + 2 :
        ].startswith(prefix)
        if already_prefixed:
            continue
        page.title = f"{prefix}. {page.title}"
