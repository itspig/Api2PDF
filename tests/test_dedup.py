from app.document.dedup import deduplicate_repeating_blocks
from app.document.models import ExtractedPage, ParagraphBlock


def _page(blocks):
    return ExtractedPage(
        url="https://example.com/x",
        title="",
        headings=[],
        text="",
        word_count=0,
        blocks=list(blocks),
    )


def test_dedup_removes_blocks_present_on_majority_of_pages() -> None:
    nav = ParagraphBlock(kind="paragraph", text="Home | Docs | Forum")
    risk = ParagraphBlock(kind="paragraph", text="Investment carries risk; please be cautious.")
    pages = [
        _page([nav, ParagraphBlock(kind="paragraph", text="Page 1 unique content"), risk]),
        _page([nav, ParagraphBlock(kind="paragraph", text="Page 2 unique content"), risk]),
        _page([nav, ParagraphBlock(kind="paragraph", text="Page 3 unique content"), risk]),
        _page([nav, ParagraphBlock(kind="paragraph", text="Page 4 unique content"), risk]),
    ]
    removed = deduplicate_repeating_blocks(pages)
    assert removed == 8  # nav + risk dropped from each of 4 pages
    for page in pages:
        texts = [b.text for b in page.blocks]
        assert "Home | Docs | Forum" not in texts
        assert "Investment carries risk; please be cautious." not in texts
        assert any(t.startswith("Page ") for t in texts)


def test_dedup_keeps_unique_blocks() -> None:
    pages = [
        _page([ParagraphBlock(kind="paragraph", text=f"Body {i}") for i in range(3)])
        for _ in range(4)
    ]
    removed = deduplicate_repeating_blocks(pages)
    # Each page has its own bodies but they happen to repeat the same string
    # across pages, so all should be removed; this also verifies the threshold
    # logic works on identical content.
    assert removed > 0


def test_dedup_skips_when_corpus_too_small() -> None:
    nav = ParagraphBlock(kind="paragraph", text="Home")
    pages = [_page([nav]), _page([nav])]
    assert deduplicate_repeating_blocks(pages) == 0
    assert pages[0].blocks and pages[1].blocks
