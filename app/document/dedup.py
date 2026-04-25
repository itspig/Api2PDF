"""Cross-page block deduplication.

Real-world documentation sites embed the same boilerplate on every page:
left-side navigation, footer, copyright, "risk disclosure" sections, etc.
After our extractor pulls these into block lists, they explode the resulting
PDF and bury the actual per-page content.

This module identifies blocks that repeat across many pages and removes them
in-place. The heuristic is intentionally simple and conservative:

* fingerprint each block by its (kind, normalized-text) tuple,
* count fingerprints across pages (each fingerprint contributes at most once
  per page so a single page that lists "FAQ" twice doesn't trigger),
* drop fingerprints that occur on >= ``threshold_ratio`` of pages, *unless*
  the corpus has fewer than 3 pages (then dedup is skipped because we don't
  have enough samples to be confident).

We never deduplicate ImageBlocks because the same diagram occasionally
illustrates multiple chapters intentionally; users can rely on the simple
text-block dedup to clean obvious repeated nav/footer text.
"""

from __future__ import annotations

from app.document.models import (
    Block,
    ExtractedPage,
    ParagraphBlock,
)


def _fingerprint(block: Block) -> tuple[str, str] | None:
    """Return a fingerprint suitable for boilerplate detection.

    We deliberately fingerprint **only paragraphs** because:
      * Headings repeated across chapters are real content (e.g. "Prerequisites").
      * Code samples repeated across chapters are real content (e.g. an import line).
      * Tables repeated across chapters are real content (e.g. a parameter
        reference embedded in multiple sections).

    Repeated boilerplate that hurts readability is almost always paragraph
    text (nav text, copyright, risk disclosure, footer rows). Restricting
    fingerprinting here keeps the dedup pass safe by default.
    """

    if isinstance(block, ParagraphBlock):
        return ("paragraph", " ".join(block.text.split()))
    return None


def deduplicate_repeating_blocks(
    pages: list[ExtractedPage],
    *,
    threshold_ratio: float = 0.6,
    min_pages: int = 3,
) -> int:
    """Remove blocks that appear on a strict majority of pages.

    A block is considered "repeating" only if it shows up on *more than*
    ``threshold_ratio`` of the pages **and** on at least 3 distinct pages.
    The ``> threshold`` (rather than ``>=``) bound prevents legitimate
    cross-references shared by two of three sibling chapters from being
    silently dropped.

    Returns the total number of block instances removed.
    """

    if len(pages) < min_pages:
        return 0

    occurrence: dict[tuple[str, str], int] = {}
    for page in pages:
        seen: set[tuple[str, str]] = set()
        for block in page.blocks:
            fp = _fingerprint(block)
            if fp is None or fp in seen:
                continue
            seen.add(fp)
            occurrence[fp] = occurrence.get(fp, 0) + 1

    page_count = len(pages)
    threshold = max(3, page_count * threshold_ratio)
    repeating = {fp for fp, count in occurrence.items() if count > threshold}
    if not repeating:
        return 0

    removed = 0
    for page in pages:
        kept: list[Block] = []
        for block in page.blocks:
            fp = _fingerprint(block)
            if fp is not None and fp in repeating:
                removed += 1
                continue
            kept.append(block)
        page.blocks = kept
    return removed
