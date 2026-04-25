"""Release-hardening tests (1.0).

These were written first (TDD red) to pin invariants we want to ship.
Each test corresponds to a real audit finding from the pre-release review.
"""

from io import BytesIO
from pathlib import Path

import pytest

from app.document.dedup import deduplicate_repeating_blocks
from app.document.models import (
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ImageBlock,
    ParagraphBlock,
)
from app.document.titles import strip_site_suffix
from app.exporter.pdf_exporter import export_pdf
from app.parser.urls import normalize_url


# -- normalize_url -----------------------------------------------------------


def test_normalize_url_strips_default_http_port() -> None:
    assert normalize_url("HTTP://Example.COM:80/x/") == "http://example.com/x/"


def test_normalize_url_strips_default_https_port() -> None:
    assert normalize_url("HTTPS://Example.COM:443/x/") == "https://example.com/x/"


def test_normalize_url_keeps_non_default_port() -> None:
    assert normalize_url("https://example.com:8080/x/") == "https://example.com:8080/x/"


# -- dedup threshold ---------------------------------------------------------


def _para_page(*texts: str) -> ExtractedPage:
    return ExtractedPage(
        url="x",
        title="",
        headings=[],
        text="",
        word_count=0,
        blocks=[ParagraphBlock(text=t) for t in texts],
    )


def test_dedup_does_not_drop_two_of_three_blocks() -> None:
    """A block that appears on 2 of 3 pages must NOT be dropped.

    Otherwise legitimate cross-references (an intro paragraph reused by two
    sibling chapters) would silently disappear from the output PDF.
    """

    pages = [
        _para_page("intro shared by two chapters", "page-1 unique body"),
        _para_page("intro shared by two chapters", "page-2 unique body"),
        _para_page("page-3 unique body"),
    ]
    removed = deduplicate_repeating_blocks(pages)
    assert removed == 0
    assert any(
        any(b.text == "intro shared by two chapters" for b in p.blocks) for p in pages
    )


def test_dedup_drops_block_present_on_all_pages() -> None:
    pages = [
        _para_page("nav", f"unique-{i}") for i in range(5)
    ]
    removed = deduplicate_repeating_blocks(pages)
    assert removed == 5
    for page in pages:
        assert all(b.text != "nav" for b in page.blocks)


def test_dedup_does_not_drop_image_blocks() -> None:
    """Images that recur (logo, mascot) shouldn't be silently removed."""

    img = ImageBlock(src="https://example.com/logo.png", alt="logo")

    def page_with_logo(extra_text: str) -> ExtractedPage:
        return ExtractedPage(
            url="x",
            title="",
            headings=[],
            text="",
            word_count=0,
            blocks=[
                ImageBlock(src=img.src, alt=img.alt),
                ParagraphBlock(text=extra_text),
            ],
        )

    pages = [page_with_logo(f"chapter {i}") for i in range(5)]
    deduplicate_repeating_blocks(pages)
    for page in pages:
        assert any(isinstance(b, ImageBlock) for b in page.blocks)


# -- title cleanup -----------------------------------------------------------


def test_strip_site_suffix_handles_empty_input() -> None:
    assert strip_site_suffix([]) == []


def test_strip_site_suffix_does_not_overstrip_when_no_separator() -> None:
    """Titles without our separators must come back unchanged."""

    titles = ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert strip_site_suffix(titles) == titles


# -- exporter robustness -----------------------------------------------------


def test_export_pdf_with_zero_pages_still_writes_valid_pdf(tmp_path: Path) -> None:
    """Defensive: a document with no pages should still emit a valid PDF.

    The pipeline already refuses to call us in that case, but the exporter
    must not raise -- third-party callers rely on this contract.
    """

    output = tmp_path / "empty.pdf"
    document = CompiledDocument(
        site_title="Empty",
        source_url="https://example.com/",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[],
    )
    export_pdf(document, str(output))
    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF-")


def test_export_pdf_with_only_failed_image_falls_back_gracefully(tmp_path: Path) -> None:
    """If every ImageBlock failed to download (data is None), the exporter
    must still produce a valid PDF -- and ideally still embed the alt text."""

    page = ExtractedPage(
        url="https://example.com/",
        title="Imageless",
        headings=["Imageless"],
        text="alt text",
        word_count=2,
        blocks=[
            HeadingBlock(level=1, text="Imageless"),
            ImageBlock(src="https://example.com/missing.png", alt="missing diagram"),
        ],
    )
    document = CompiledDocument(
        site_title="Example",
        source_url="https://example.com/",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[page],
    )
    output = tmp_path / "alt.pdf"
    export_pdf(document, str(output))
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    # No XObject was emitted because we never had image bytes.
    assert b"/Subtype /Image" not in data


def test_double_export_in_same_process_does_not_explode(tmp_path: Path) -> None:
    """Font registration must be idempotent across successive export_pdf calls.

    A daemon or test runner that exports many PDFs in one process previously
    risked a ValueError("font already registered") on second call.
    """

    page = ExtractedPage(
        url="https://example.com/",
        title="Repeat",
        headings=["Repeat"],
        text="hi",
        word_count=1,
        blocks=[ParagraphBlock(text="hi")],
    )
    doc = CompiledDocument(
        site_title="Repeat",
        source_url="https://example.com/",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[page],
    )
    for i in range(3):
        out = tmp_path / f"r-{i}.pdf"
        export_pdf(doc, str(out))
        assert out.read_bytes().startswith(b"%PDF-")


# -- image fetcher payload validation ---------------------------------------


def test_image_fetcher_payload_validation_is_safe_with_pillow_verify() -> None:
    """``Image.verify()`` consumes the underlying buffer; the fetcher must
    keep the original bytes intact so reportlab can decode them later."""

    import base64

    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAAWgmWQ0"
        "AAAAASUVORK5CYII="
    )
    from app.net.image_fetcher import _is_supported_payload

    assert _is_supported_payload(png_bytes, "image/png") is True

    # The bytes object is unmodified after the validation pass.
    from reportlab.platypus import Image as RLImage

    img = RLImage(BytesIO(png_bytes))
    img._restrictSize(72, 72)
    assert img.drawWidth > 0


# -- skip-rule sanity --------------------------------------------------------


def test_should_skip_url_drops_wp_login_query_redirects() -> None:
    """Default skip rules must reject /wp-login.php?redirect_to=... links."""

    from app.config.models import ExportConfig
    from app.parser.filters import should_skip_url

    config = ExportConfig(url="https://example.com/docs/")
    assert should_skip_url(
        "https://example.com/wp-login.php?redirect_to=%2Fdocs%2F", config
    )
    assert should_skip_url(
        "https://example.com/docs/?action=share&replytocom=42", config
    )


def test_should_skip_url_keeps_legitimate_chinese_path() -> None:
    """Percent-encoded Chinese paths under the doc prefix must NOT be skipped."""

    from app.config.models import ExportConfig
    from app.parser.filters import should_skip_url

    config = ExportConfig(url="https://khsci.com/khQuant/chapter1/")
    assert not should_skip_url(
        "https://khsci.com/khQuant/%e5%9f%ba%e6%9c%ac%e9%9d%a2%e6%95%b0%e6%8d%ae/",
        config,
    )


# -- Oracle review: Block.kind invariants -----------------------------------


def test_block_kind_is_locked_to_literal_value() -> None:
    """Each Block dataclass must default ``kind`` so callers cannot smuggle
    in a wrong value (e.g. ``HeadingBlock(...)``)."""

    h = HeadingBlock(level=1, text="x")
    assert h.kind == "heading"
    p = ParagraphBlock(text="x")
    assert p.kind == "paragraph"
    img = ImageBlock(src="x", alt="y")
    assert img.kind == "image"


# -- Oracle review: dedup must NOT remove headings / code / tables ----------


def test_dedup_keeps_repeated_headings() -> None:
    """A heading shared across many chapters (e.g. an H2 that's the same on
    every page of a tutorial series) is real content; only paragraph-level
    boilerplate should be removed."""

    from app.document.dedup import deduplicate_repeating_blocks

    pages = [
        ExtractedPage(
            url=f"https://example.com/{i}",
            title="",
            headings=[],
            text="",
            word_count=0,
            blocks=[
                HeadingBlock(level=2, text="Prerequisites"),
                ParagraphBlock(text=f"unique-paragraph-{i}"),
            ],
        )
        for i in range(6)
    ]
    deduplicate_repeating_blocks(pages)
    for page in pages:
        assert any(isinstance(b, HeadingBlock) for b in page.blocks), (
            "headings must be preserved even when shared across pages"
        )


def test_dedup_keeps_repeated_code_blocks() -> None:
    """A boilerplate import line repeated across chapters is documentation,
    not navigation; we must keep it."""

    from app.document.dedup import deduplicate_repeating_blocks
    from app.document.models import CodeBlock

    pages = [
        ExtractedPage(
            url=f"https://example.com/{i}",
            title="",
            headings=[],
            text="",
            word_count=0,
            blocks=[
                CodeBlock(text="from xtquant import xtdata", language="python"),
                ParagraphBlock(text=f"discussion paragraph {i}"),
            ],
        )
        for i in range(6)
    ]
    deduplicate_repeating_blocks(pages)
    for page in pages:
        assert any(isinstance(b, CodeBlock) for b in page.blocks), (
            "code samples must never be dropped by dedup"
        )


# -- Oracle review: image-only pages survive --------------------------------


def test_extractor_emits_alt_text_so_image_only_pages_survive() -> None:
    """If a page is essentially a screenshot with alt text, ``extract_page``
    must emit at least one block whose ``text`` lets the pipeline detect it
    as non-empty content."""

    from app.parser.extractor import extract_page

    html = """
    <html><body><article>
      <img src='/x.png' alt='diagram of the trading flow' />
    </article></body></html>
    """
    page = extract_page("https://example.com/p", html)
    assert page.text.strip(), "image-only page should still produce flat text"


# -- Oracle review: UA carries api2pdf identifier ---------------------------


def test_default_user_agent_advertises_api2pdf() -> None:
    """The browser-like UA must still carry an ``api2pdf/<version>`` token so
    operators can recognise our traffic in their logs."""

    from app.core.constants import DEFAULT_USER_AGENT
    from app.version import __version__

    assert "api2pdf" in DEFAULT_USER_AGENT.lower()
    assert __version__ in DEFAULT_USER_AGENT
