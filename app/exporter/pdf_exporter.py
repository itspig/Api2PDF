from html import escape
from io import BytesIO
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
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


CODE_BACKGROUND = colors.HexColor("#1e1e1e")
CODE_HEADER_BACKGROUND = colors.HexColor("#2d2d2d")
CODE_HEADER_BORDER = colors.HexColor("#3c3c3c")
CODE_TEXT_COLOR = colors.HexColor("#f8f8f2")
CODE_LANGUAGE_COLOR = colors.HexColor("#9cdcfe")

from app.core.errors import PdfExportError
from app.document.models import (
    Block,
    CodeBlock,
    CompiledDocument,
    ExtractedPage,
    HeadingBlock,
    ImageBlock,
    ParagraphBlock,
    TableBlock,
)


FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_CANDIDATES = [
    FONT_DIR / "NotoSansSC-Regular.ttf",
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simsun.ttc"),
]
# Code-friendly monospace fonts. We prefer CJK-aware monospace faces because
# api2pdf is frequently used on Chinese documentation; ASCII-only mono fonts
# (Consolas/Courier) drop Chinese glyphs inside <pre>/<code> blocks. The
# CJK-capable body fonts at the bottom keep code listings readable even when
# no monospaced CJK font is installed - glyphs render correctly, slightly less
# crisp than a true monospace.
MONO_FONT_CANDIDATES = [
    FONT_DIR / "SarasaMono-Regular.ttf",
    Path("C:/Windows/Fonts/sarasa-mono-sc-regular.ttf"),
    Path("C:/Windows/Fonts/CascadiaMono.ttf"),
    Path("C:/Windows/Fonts/CascadiaCode.ttf"),
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


def _font_supports_cjk(font_path: Path) -> bool:
    """Quick heuristic: does this font cover the Basic CJK block?"""

    try:
        from reportlab.pdfbase.ttfonts import TTFontFile

        ttf = TTFontFile(str(font_path))
        cmap = getattr(ttf, "charToGlyph", {}) or {}
        # Cover at least a couple of common CJK codepoints (中 文)
        return all(ord(ch) in cmap for ch in "\u4e2d\u6587")
    except Exception:
        return False


def _register_mono_font(unicode_font_fallback: str) -> str:
    """Register a code font that can render both ASCII and CJK glyphs.

    We try our preferred mono fonts first, but a candidate is only accepted if
    it actually supports CJK. Otherwise we fall back to the already-registered
    Unicode body font so Chinese characters never silently disappear from code.
    """

    for font_path in MONO_FONT_CANDIDATES:
        if not font_path.exists():
            continue
        if not _font_supports_cjk(font_path):
            continue
        font_name = "Api2PdfMono"
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            return font_name
        except Exception:
            continue
    return unicode_font_fallback


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


_LANGUAGE_ALIASES = {
    "py": "Python",
    "python3": "Python",
    "python": "Python",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "sh": "Shell",
    "bash": "Bash",
    "shell": "Shell",
    "zsh": "Zsh",
    "ps": "PowerShell",
    "powershell": "PowerShell",
    "ps1": "PowerShell",
    "json": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "html": "HTML",
    "css": "CSS",
    "sql": "SQL",
    "c": "C",
    "cpp": "C++",
    "c++": "C++",
    "java": "Java",
    "go": "Go",
    "rs": "Rust",
    "rust": "Rust",
    "vba": "VBA",
}


def _normalize_language_label(language: str) -> str:
    """Return a friendly language label, or empty string when unknown."""

    if not language:
        return ""
    cleaned = language.strip()
    if not cleaned:
        return ""
    return _LANGUAGE_ALIASES.get(cleaned.lower(), cleaned[:1].upper() + cleaned[1:])


def _build_code_language_strip(
    language_label: str,
    *,
    doc_width: float,
    code_language_style: ParagraphStyle,
) -> Flowable:
    paragraph = Paragraph(_escape_inline(language_label), code_language_style)
    table = Table(
        [[paragraph]],
        colWidths=[doc_width],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CODE_HEADER_BACKGROUND),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, CODE_HEADER_BORDER),
                ("BOX", (0, 0), (-1, -1), 0.5, CODE_HEADER_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


class _DarkCodeBlock(Flowable):
    """Flowable that paints a solid dark background behind a Preformatted body.

    ReportLab's `Preformatted` only paints the `backColor` directly behind text
    glyphs, leaving padding and trailing whitespace white. We wrap the body in a
    Flowable that draws a single filled rectangle covering the full block area,
    then renders the Preformatted on top. We delegate ``wrap`` and ``split`` to
    the wrapped flowable so very long code blocks still page-break naturally.
    """

    PADDING_X = 8
    PADDING_Y = 6

    def __init__(self, body: Flowable, *, doc_width: float) -> None:
        super().__init__()
        self.body = body
        self.doc_width = doc_width
        self.width = doc_width
        self.height = 0

    # Allow ReportLab to call wrap repeatedly during layout
    def wrap(self, available_width, available_height):
        inner_width = self.doc_width - 2 * self.PADDING_X
        inner_height_available = available_height - 2 * self.PADDING_Y
        body_w, body_h = self.body.wrap(inner_width, max(inner_height_available, 0))
        self.width = self.doc_width
        self.height = body_h + 2 * self.PADDING_Y
        return self.width, self.height

    def split(self, available_width, available_height):
        inner_height = max(available_height - 2 * self.PADDING_Y, 0)
        if inner_height <= 0:
            return []
        parts = self.body.split(self.doc_width - 2 * self.PADDING_X, inner_height)
        if not parts:
            return []
        wrapped: list[Flowable] = []
        for part in parts:
            wrapped.append(_DarkCodeBlock(part, doc_width=self.doc_width))
        return wrapped

    def draw(self) -> None:
        canvas = self.canv
        canvas.saveState()
        canvas.setFillColor(CODE_BACKGROUND)
        canvas.setStrokeColor(CODE_HEADER_BORDER)
        canvas.setLineWidth(0.5)
        canvas.rect(0, 0, self.width, self.height, stroke=1, fill=1)
        canvas.restoreState()
        self.body.drawOn(canvas, self.PADDING_X, self.PADDING_Y)


def _build_code_body(
    code_text: str,
    *,
    doc_width: float,
    code_style: ParagraphStyle,
) -> Flowable:
    if not code_text:
        return Spacer(1, 0)
    body = Preformatted(code_text, code_style, dedent=0)
    return _DarkCodeBlock(body, doc_width=doc_width)


def _build_code_flowable(
    block: CodeBlock,
    *,
    doc_width: float,
    code_style: ParagraphStyle,
    code_language_style: ParagraphStyle,
) -> KeepTogether:
    """Return a KeepTogether wrapping a small head + body so callers/tests can introspect."""

    flowables = _build_code_flowables(
        block,
        doc_width=doc_width,
        code_style=code_style,
        code_language_style=code_language_style,
    )
    return KeepTogether(flowables)


def _build_code_flowables(
    block: CodeBlock,
    *,
    doc_width: float,
    code_style: ParagraphStyle,
    code_language_style: ParagraphStyle,
) -> list[Flowable]:
    language_label = _normalize_language_label(block.language)
    code_text = block.text.replace("\t", "    ").rstrip()
    body = _build_code_body(code_text, doc_width=doc_width, code_style=code_style)

    flowables: list[Flowable] = [Spacer(1, 0.1 * cm)]
    if language_label:
        header = _build_code_language_strip(
            language_label,
            doc_width=doc_width,
            code_language_style=code_language_style,
        )
        # Keep the language strip glued to the first body line; long bodies
        # still split naturally because only the header pair is held together.
        flowables.append(KeepTogether([header, Spacer(1, 0.05 * cm)]))
    flowables.append(body)
    flowables.append(Spacer(1, 0.25 * cm))
    return flowables


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

    ReportLab requires ``addOutlineEntry`` to never jump *down* more than one
    level from the previous entry. We map each HTML heading level to a PDF
    outline depth that:

    * starts at ``base_level`` for the first heading,
    * never increases by more than 1 compared to the previously emitted level,
    * preserves relative hierarchy (a deeper HTML heading produces a deeper
      outline level than a shallower one within the same scope).
    """

    def __init__(self, base_level: int = 1) -> None:
        self.base_level = base_level
        self._stack: list[tuple[int, int]] = []  # (html_level, outline_level)
        self._last_emitted = base_level - 1

    def outline_level(self, html_level: int) -> int:
        # Pop the stack down to a heading whose html_level is shallower than
        # the new heading (sibling/uncle relationship).
        while self._stack and self._stack[-1][0] >= html_level:
            self._stack.pop()
        if self._stack:
            parent_outline = self._stack[-1][1]
            target = parent_outline + 1
        else:
            target = self.base_level
        # Never jump more than one level deeper than the last entry we emitted.
        target = min(target, self._last_emitted + 1)
        target = max(self.base_level, target)
        self._stack.append((html_level, target))
        self._last_emitted = target
        return target


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
    doc_height: float,
    body_style: ParagraphStyle,
    code_style: ParagraphStyle,
    code_language_style: ParagraphStyle,
    meta_style: ParagraphStyle,
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
        flowables.extend(
            _build_code_flowables(
                block,
                doc_width=doc_width,
                code_style=code_style,
                code_language_style=code_language_style,
            )
        )
    elif isinstance(block, TableBlock):
        flowables.append(_build_table_flowable(block, doc_width=doc_width, body_style=body_style))
    elif isinstance(block, ImageBlock):
        flowables.extend(
            _build_image_flowables(
                block,
                doc_width=doc_width,
                doc_height=doc_height,
                body_style=body_style,
                meta_style=meta_style,
            )
        )
    return flowables


def _build_image_flowables(
    block: ImageBlock,
    *,
    doc_width: float,
    doc_height: float,
    body_style: ParagraphStyle,
    meta_style: ParagraphStyle,
) -> list[Flowable]:
    if not block.data:
        # No payload (download failed or --no-images): show alt-text fallback
        # so the reader knows an image was present at this position.
        if block.alt:
            return [
                Paragraph(_escape_inline(f"[image: {block.alt}]"), meta_style),
                Spacer(1, 0.2 * cm),
            ]
        return []
    try:
        buffer = BytesIO(block.data)
        image = Image(buffer)
        max_width = doc_width
        # Cap height so a single image cannot consume an entire page; reportlab
        # renders the leftover content on the next page.
        max_height = max(2 * cm, doc_height * 0.7)
        image._restrictSize(max_width, max_height)
        image.hAlign = "CENTER"
    except Exception:
        if block.alt:
            return [
                Paragraph(_escape_inline(f"[image: {block.alt}]"), meta_style),
                Spacer(1, 0.2 * cm),
            ]
        return []

    flowables: list[Flowable] = [Spacer(1, 0.2 * cm), image]
    if block.alt:
        flowables.append(Paragraph(_escape_inline(block.alt), meta_style))
    flowables.append(Spacer(1, 0.3 * cm))
    return flowables


def export_pdf(document: CompiledDocument, output_path: str) -> None:
    try:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        body_font = _register_unicode_font()
        mono_font = _register_mono_font(body_font)
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
            textColor=CODE_TEXT_COLOR,
            leftIndent=0,
            rightIndent=0,
            spaceBefore=0,
            spaceAfter=0,
        )
        code_language_style = ParagraphStyle(
            "ApiCodeLanguage",
            parent=styles["BodyText"],
            fontName=mono_font,
            fontSize=8,
            leading=10,
            textColor=CODE_LANGUAGE_COLOR,
            spaceBefore=0,
            spaceAfter=0,
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
        doc_height = doc.height

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
                        doc_height=doc_height,
                        body_style=body_style,
                        code_style=code_style,
                        code_language_style=code_language_style,
                        meta_style=meta_style,
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
