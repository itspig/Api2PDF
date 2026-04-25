from pathlib import Path

from app.document.models import (
    CodeBlock,
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
)
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import KeepTogether, Table

from app.exporter.pdf_exporter import (
    CODE_BACKGROUND,
    CODE_HEADER_BACKGROUND,
    _build_code_flowable,
    _normalize_language_label,
    export_pdf,
)


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


def test_normalize_language_label_handles_aliases() -> None:
    assert _normalize_language_label("python") == "Python"
    assert _normalize_language_label("py") == "Python"
    assert _normalize_language_label("JS") == "JavaScript"
    assert _normalize_language_label("") == "TEXT"
    assert _normalize_language_label("custom-lang") == "Custom-lang"


def test_build_code_flowable_uses_dark_theme_with_language_header() -> None:
    from reportlab.platypus import Preformatted

    styles = getSampleStyleSheet()
    code_style = ParagraphStyle(
        "ApiCodeTest",
        parent=styles["Code"],
        fontName="Courier",
        backColor=CODE_BACKGROUND,
    )
    code_language_style = ParagraphStyle("ApiCodeLanguageTest", parent=styles["BodyText"])
    block = CodeBlock(
        kind="code",
        text="def on_data(datas):\n    for stock_code in datas:\n        print(stock_code, datas[stock_code])",
        language="python",
    )
    flowable = _build_code_flowable(
        block,
        doc_width=500,
        code_style=code_style,
        code_language_style=code_language_style,
    )
    assert isinstance(flowable, KeepTogether)

    def _iter_flat(node):
        if isinstance(node, KeepTogether):
            for item in node._content:
                yield from _iter_flat(item)
        else:
            yield node

    items = list(_iter_flat(flowable))
    header_tables = [item for item in items if isinstance(item, Table)]
    assert header_tables, "code flowable must contain a header Table"
    header = header_tables[0]
    assert header._argW == [500]
    header_backgrounds = [cmd for cmd in header._bkgrndcmds if cmd[0] == "BACKGROUND"]
    header_colors = {cmd[3] for cmd in header_backgrounds}
    assert CODE_HEADER_BACKGROUND in header_colors

    pre_blocks = [item for item in items if isinstance(item, Preformatted)]
    assert pre_blocks, "code flowable must contain a Preformatted body"
    body_style = pre_blocks[0].style
    assert body_style.backColor == CODE_BACKGROUND


def test_export_pdf_code_block_renders(tmp_path: Path) -> None:
    page = ExtractedPage(
        url="https://example.com/docs/code",
        title="Code Sample",
        headings=["Code Sample"],
        text="def on_data(datas):\n    print(datas)",
        word_count=5,
        blocks=[
            HeadingBlock(kind="heading", level=1, text="Code Sample"),
            CodeBlock(
                kind="code",
                text="def on_data(datas):\n    for stock_code in datas:\n        print(stock_code, datas[stock_code])",
                language="python",
            ),
        ],
    )
    document = CompiledDocument(
        site_title="API Documentation - example.com",
        source_url="https://example.com/docs/code",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[page],
    )
    output = tmp_path / "code.pdf"
    export_pdf(document, str(output))
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    assert b"/Type /Page" in data
