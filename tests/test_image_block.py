from pathlib import Path

from app.document.models import (
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ImageBlock,
    ParagraphBlock,
)
from app.exporter.pdf_exporter import export_pdf
from app.parser.extractor import extract_page


HTML_WITH_IMAGE = """
<html><head><title>With image</title></head><body>
  <article>
    <h1>Demo</h1>
    <p>Intro paragraph.</p>
    <img src="/assets/diagram.png" alt="Diagram of pipeline" />
    <img src="data:image/svg+xml;base64,PHN2Zy8+" alt="ignore me" />
    <img src="icon.svg" alt="ignore svg" />
  </article>
</body></html>
"""


def test_extract_page_emits_image_blocks_and_skips_data_and_svg() -> None:
    page = extract_page("https://example.com/docs/demo", HTML_WITH_IMAGE)
    image_blocks = [b for b in page.blocks if b.kind == "image"]
    assert len(image_blocks) == 1
    assert image_blocks[0].src == "https://example.com/assets/diagram.png"
    assert image_blocks[0].alt == "Diagram of pipeline"


def _png_bytes() -> bytes:
    # Minimal valid 1x1 PNG (transparent) so reportlab can decode it.
    import base64

    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAAWgmWQ0"
        "AAAAASUVORK5CYII="
    )
    return base64.b64decode(b64)


def test_export_pdf_renders_image_block(tmp_path: Path) -> None:
    page = ExtractedPage(
        url="https://example.com/docs/demo",
        title="Demo",
        headings=["Demo"],
        text="Demo image",
        word_count=2,
        blocks=[
            HeadingBlock(kind="heading", level=1, text="Demo"),
            ParagraphBlock(kind="paragraph", text="Diagram below."),
            ImageBlock(
                kind="image",
                src="https://example.com/assets/diagram.png",
                alt="Diagram",
                data=_png_bytes(),
                mime_type="image/png",
            ),
        ],
    )
    document = CompiledDocument(
        site_title="Example",
        source_url="https://example.com/docs/demo",
        generated_at="2025-01-01 00:00:00 UTC",
        pages=[page],
    )
    output = tmp_path / "with_image.pdf"
    export_pdf(document, str(output))
    data = output.read_bytes()
    assert data.startswith(b"%PDF-")
    # An XObject image and a corresponding image dictionary should land in the file.
    assert b"/Subtype /Image" in data
    assert b"/Type /XObject" in data
