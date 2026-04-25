from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.core.errors import PdfExportError
from app.document.models import CompiledDocument


FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_CANDIDATES = [
    FONT_DIR / "NotoSansSC-Regular.ttf",
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]


def _register_font() -> str:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            font_name = "Api2PdfUnicode"
            try:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                return font_name
            except Exception:
                continue
    return "Helvetica"


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    page_text = f"Page {doc.page}"
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, page_text)
    canvas.restoreState()


def _paragraphs_from_text(text: str, style: ParagraphStyle) -> list[Paragraph | Spacer]:
    flowables: list[Paragraph | Spacer] = []
    buffer: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer:
                flowables.append(Paragraph("<br/>".join(buffer), style))
                flowables.append(Spacer(1, 0.15 * cm))
                buffer = []
            continue
        escaped = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        buffer.append(escaped)
        if len(buffer) >= 8:
            flowables.append(Paragraph("<br/>".join(buffer), style))
            flowables.append(Spacer(1, 0.15 * cm))
            buffer = []
    if buffer:
        flowables.append(Paragraph("<br/>".join(buffer), style))
    return flowables


def export_pdf(document: CompiledDocument, output_path: str) -> None:
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        font_name = _register_font()
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ApiTitle",
            parent=styles["Title"],
            fontName=font_name,
            alignment=TA_CENTER,
            fontSize=22,
            leading=28,
            spaceAfter=18,
        )
        heading_style = ParagraphStyle("ApiHeading", parent=styles["Heading1"], fontName=font_name, fontSize=16, leading=20, spaceAfter=10)
        body_style = ParagraphStyle("ApiBody", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=14, spaceAfter=6)
        meta_style = ParagraphStyle("ApiMeta", parent=styles["BodyText"], fontName=font_name, fontSize=8, leading=11, textColor=colors.grey)

        doc = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm)
        story = [
            Paragraph(document.site_title, title_style),
            Paragraph(f"Source: {document.source_url}", meta_style),
            Paragraph(f"Generated: {document.generated_at}", meta_style),
            Spacer(1, 1 * cm),
            Paragraph("Contents", heading_style),
        ]
        for index, page in enumerate(document.pages, start=1):
            story.append(Paragraph(f"{index}. {page.title}", body_style))
        story.append(PageBreak())

        for index, page in enumerate(document.pages, start=1):
            story.append(Paragraph(f"{index}. {page.title}", heading_style))
            story.append(Paragraph(page.url, meta_style))
            story.append(Spacer(1, 0.25 * cm))
            story.extend(_paragraphs_from_text(page.text, body_style))
            if index != len(document.pages):
                story.append(PageBreak())
        doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    except Exception as exc:
        raise PdfExportError(f"Failed to export PDF to {output_path}: {exc}") from exc
