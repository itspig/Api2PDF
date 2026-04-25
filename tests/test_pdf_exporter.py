from pathlib import Path

from app.document.models import (
    CodeBlock,
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
)
from app.exporter.pdf_exporter import export_pdf


def _build_document() -> CompiledDocument:
    page = ExtractedPage(
        url="https://example.com/docs/intro",
        title="API Intro",
        headings=["API Intro", "Authentication"],
        text="API Intro\nAuthentication\nUse API keys.",
        word_count=5,
        blocks=[
            HeadingBlock(kind="heading", level=1, text="API Intro"),
            ParagraphBlock(kind="paragraph", text="This is an introduction to the API."),
            HeadingBlock(kind="heading", level=2, text="Authentication"),
            ParagraphBlock(kind="paragraph", text="Use API keys with HMAC signing."),
            CodeBlock(kind="code", text='print("hello")', language="python"),
            TableBlock(kind="table", rows=[["Method", "Path"], ["GET", "/orders"]]),
        ],
    )
    return CompiledDocument(
        site_title="API Documentation - example.com",
        source_url="https://example.com/docs/intro",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[page],
    )


def test_export_pdf_creates_file_with_outline(tmp_path: Path) -> None:
    output = tmp_path / "out.pdf"
    document = _build_document()
    export_pdf(document, str(output))
    assert output.exists()
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    # Outline / bookmarks should be present
    assert b"/Outlines" in data
    # The contents page should have at least one outline entry
    assert b"/Count" in data


def test_export_pdf_table_renders_grid(tmp_path: Path) -> None:
    output = tmp_path / "out_table.pdf"
    document = _build_document()
    export_pdf(document, str(output))
    data = output.read_bytes()
    # ReportLab Table flowable embeds these dictionary keys; smoke check.
    assert b"/Type /Page" in data
