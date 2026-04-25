from html import escape
from pathlib import Path
import uuid

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.errors import PdfExportError
from app.document.models import (
    Block,
    CodeBlock,
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
)


FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_CANDIDATES = [
    FONT_DIR / "NotoSansSC-Regular.ttf",
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]
MONO_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/consola.ttf"),
    Path("C:/Windows/Fonts/cour.ttf"),
]


def _register_unicode_font() -> str:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            font_name = "Api2PdfUnicode"
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                return font_name
            except Exception:
                continue
    return "Helvetica"


def _register_mono_font() -> str:
    for font_path in MONO_FONT_CANDIDATES:
        if font_path.exists():
            font_name = "Api2PdfMono"
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                return font_name
            except Exception:
                continue
    return "Courier"


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    page_text = f"Page {doc.page}"
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, page_text)
    canvas.restoreState()


class _BookmarkFlowable(Flowable):
    """Zero-height flowable that registers a PDF outline entry on draw."""

    def __init__(self, key: str, title: str, level: int = 0, closed: bool = True) -> None:
        super().__init__()
        self.key = key
        self.title = title
        self.level = level
        self.closed = closed
        self.width = 0
        self.height = 0

    def wrap(self, available_width, available_height):
        return (0, 0)

    def draw(self) -> None:
        canvas = self.canv
        canvas.bookmarkPage(self.key)
        canvas.addOutlineEntry(self.title, self.key, level=self.level, closed=self.closed)


def _escape_inline(text: str) -> str:
    return escape(text, quote=False)


def _build_table_flowable(block: TableBlock, doc_width: float, body_style: ParagraphStyle) -> Flowable:
    rows = [row for row in block.rows if row]
    if not rows:
        return Spacer(1, 0)
    column_count = max(len(row) for row in rows)
    normalized: list[list[Paragraph]] = []
    for row in rows:
        padded = list(row) + [""] * (column_count - len(row))
        normalized.append([Paragraph(_escape_inline(cell), body_style) for cell in padded])
    column_widths = [doc_width / column_count] * column_count
    table = Table(normalized, colWidths=column_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdbdbd")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


class _OutlineLevelTracker:
    """Translate HTML heading levels into safe sequential PDF outline levels.

    ReportLab requires `addOutlineEntry` to never jump down more than one
    level from the previous entry. We map each HTML heading level to a
    sequential PDF outline depth that respects this constraint.
    """

    def __init__(self, base_level: int = 1) -> None:
        self.base_level = base_level
        self._max_seen = base_level - 1
        self._html_to_outline: dict[int, int] = {}

    def outline_level(self, html_level: int) -> int:
        if html_level in self._html_to_outline:
            return self._html_to_outline[html_level]
        # Pick the next available outline level, but never jump by more than 1
        next_level = min(self._max_seen + 1, max(self.base_level, html_level))
        next_level = max(self.base_level, min(next_level, self._max_seen + 1))
        self._html_to_outline[html_level] = next_level
        if next_level > self._max_seen:
            self._max_seen = next_level
        return next_level


def _heading_style_for_level(level: int, heading_styles: dict[int, ParagraphStyle]) -> ParagraphStyle:
    if level <= 1:
        return heading_styles[2]
    if level == 2:
        return heading_styles[3]
    return heading_styles[4]


def _build_block_flowables(
    block: Block,
    *,
    doc_width: float,
    body_style: ParagraphStyle,
    code_style: ParagraphStyle,
    heading_styles: dict[int, ParagraphStyle],
    page_index: int,
    block_index: int,
    outline_tracker: _OutlineLevelTracker,
) -> list[Flowable]:
    flowables: list[Flowable] = []
    if isinstance(block, HeadingBlock):
        outline_level = outline_tracker.outline_level(block.level)
        style = _heading_style_for_level(outline_level, heading_styles)
        key = f"page-{page_index}-block-{block_index}"
        flowables.append(_BookmarkFlowable(key=key, title=block.text, level=outline_level, closed=True))
        flowables.append(Paragraph(_escape_inline(block.text), style))
    elif isinstance(block, ParagraphBlock):
        flowables.append(Paragraph(_escape_inline(block.text), body_style))
    elif isinstance(block, CodeBlock):
        flowables.append(KeepTogether(Preformatted(block.text, code_style)))
    elif isinstance(block, TableBlock):
        flowables.append(_build_table_flowable(block, doc_width=doc_width, body_style=body_style))
    return flowables


def export_pdf(document: CompiledDocument, output_path: str) -> None:
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        body_font = _register_unicode_font()
        mono_font = _register_mono_font()
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ApiTitle",
            parent=styles["Title"],
            fontName=body_font,
            alignment=TA_CENTER,
            fontSize=22,
            leading=28,
            spaceAfter=18,
        )
        page_title_style = ParagraphStyle(
            "ApiPageTitle",
            parent=styles["Heading1"],
            fontName=body_font,
            fontSize=18,
            leading=22,
            spaceBefore=4,
            spaceAfter=12,
            alignment=TA_LEFT,
        )
        h2_style = ParagraphStyle(
            "ApiH2",
            parent=styles["Heading2"],
            fontName=body_font,
            fontSize=15,
            leading=19,
            spaceBefore=10,
            spaceAfter=8,
        )
        h3_style = ParagraphStyle(
            "ApiH3",
            parent=styles["Heading3"],
            fontName=body_font,
            fontSize=13,
            leading=17,
            spaceBefore=8,
            spaceAfter=6,
        )
        h4_style = ParagraphStyle(
            "ApiH4",
            parent=styles["Heading4"],
            fontName=body_font,
            fontSize=11,
            leading=15,
            spaceBefore=6,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "ApiBody",
            parent=styles["BodyText"],
            fontName=body_font,
            fontSize=10,
            leading=14,
            spaceAfter=6,
        )
        meta_style = ParagraphStyle(
            "ApiMeta",
            parent=styles["BodyText"],
            fontName=body_font,
            fontSize=8,
            leading=11,
            textColor=colors.grey,
        )
        toc_style = ParagraphStyle(
            "ApiToc",
            parent=styles["BodyText"],
            fontName=body_font,
            fontSize=10,
            leading=14,
            spaceAfter=2,
        )
        code_style = ParagraphStyle(
            "ApiCode",
            parent=styles["Code"],
            fontName=mono_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#212121"),
            backColor=colors.HexColor("#f5f5f5"),
            borderColor=colors.HexColor("#dddddd"),
            borderWidth=0.5,
            borderPadding=6,
            leftIndent=4,
            rightIndent=4,
            spaceBefore=4,
            spaceAfter=8,
        )
        heading_styles = {2: h2_style, 3: h3_style, 4: h4_style}

        doc = SimpleDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=1.6 * cm,
            leftMargin=1.6 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
        )
        doc_width = doc.width

        story: list[Flowable] = [
            Paragraph(_escape_inline(document.site_title), title_style),
            Paragraph(_escape_inline(f"Source: {document.source_url}"), meta_style),
            Paragraph(_escape_inline(f"Generated: {document.generated_at}"), meta_style),
            Spacer(1, 1 * cm),
            Paragraph("Contents", page_title_style),
        ]

        page_keys: list[str] = []
        for index, page in enumerate(document.pages, start=1):
            page_key = f"page-{index}-{uuid.uuid4().hex[:8]}"
            page_keys.append(page_key)
            entry_text = f"{index}. {page.title}"
            story.append(
                Paragraph(
                    f'<a href="#{page_key}" color="#1a73e8">{_escape_inline(entry_text)}</a>',
                    toc_style,
                )
            )
        story.append(PageBreak())

        for index, page in enumerate(document.pages, start=1):
            page_key = page_keys[index - 1]
            page_title = f"{index}. {page.title}"
            # Top-level bookmark for the page
            story.append(_BookmarkFlowable(key=page_key, title=page_title, level=0, closed=False))
            story.append(Paragraph(_escape_inline(page_title), page_title_style))
            story.append(Paragraph(_escape_inline(page.url), meta_style))
            story.append(Spacer(1, 0.25 * cm))

            blocks = page.blocks or _fallback_blocks_from_text(page)
            outline_tracker = _OutlineLevelTracker(base_level=1)
            for block_index, block in enumerate(blocks, start=1):
                story.extend(
                    _build_block_flowables(
                        block,
                        doc_width=doc_width,
                        body_style=body_style,
                        code_style=code_style,
                        heading_styles=heading_styles,
                        page_index=index,
                        block_index=block_index,
                        outline_tracker=outline_tracker,
                    )
                )
            if index != len(document.pages):
                story.append(PageBreak())

        doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    except Exception as exc:
        raise PdfExportError(f"Failed to export PDF to {output_path}: {exc}") from exc


def _fallback_blocks_from_text(page: ExtractedPage) -> list[Block]:
    blocks: list[Block] = []
    for line in page.text.splitlines():
        cleaned = line.strip()
        if cleaned:
            blocks.append(ParagraphBlock(kind="paragraph", text=cleaned))
    return blocks
