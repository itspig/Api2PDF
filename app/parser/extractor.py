from app.core.constants import DOCUMENT_SELECTORS
from app.document.models import (
    Block,
    CodeBlock,
    ExtractedPage,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
)


CONTENT_ROOT_FALLBACKS = ["article", "main", "body"]
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK_LEVEL_TAGS = {"p", "li", "blockquote", "dt", "dd"}
SKIP_TAGS = {"script", "style", "nav", "footer", "aside", "noscript", "svg", "form", "header"}


def _make_soup(html: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml")


def _title_from_soup(soup, url: str) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    return url


def _clean_soup(soup) -> None:
    for tag in soup.find_all(list(SKIP_TAGS)):
        tag.decompose()


def _select_content_root(soup):
    from bs4 import Tag

    for selector in DOCUMENT_SELECTORS:
        node = soup.select_one(selector)
        if isinstance(node, Tag) and node.get_text(strip=True):
            return node
    for tag in CONTENT_ROOT_FALLBACKS:
        node = soup.find(tag)
        if isinstance(node, Tag) and node.get_text(strip=True):
            return node
    return soup


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _table_rows(table) -> list[list[str]]:
    from bs4 import Tag

    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return rows


def _walk_blocks(root) -> list[Block]:
    from bs4 import Tag

    blocks: list[Block] = []
    seen_pre_ids: set[int] = set()

    def emit_paragraph(text: str) -> None:
        cleaned = _normalize_text(text)
        if cleaned:
            blocks.append(ParagraphBlock(kind="paragraph", text=cleaned))

    for descendant in root.descendants:
        if not isinstance(descendant, Tag):
            continue
        name = descendant.name.lower() if descendant.name else ""
        if name in SKIP_TAGS:
            continue

        # Skip nodes that live inside a <pre> we've already emitted
        ancestor_pre = descendant.find_parent("pre")
        if ancestor_pre is not None and id(ancestor_pre) in seen_pre_ids:
            continue
        ancestor_table = descendant.find_parent("table")
        if ancestor_table is not None and ancestor_table is not descendant:
            # Cells are handled by their parent <table>
            continue

        if name in HEADING_TAGS:
            text = _normalize_text(descendant.get_text(" ", strip=True))
            if text:
                blocks.append(HeadingBlock(kind="heading", level=int(name[1]), text=text))
            continue

        if name == "pre":
            seen_pre_ids.add(id(descendant))
            code_text = descendant.get_text("\n", strip=False)
            code_text = code_text.strip("\n")
            language = ""
            inner_code = descendant.find("code")
            if isinstance(inner_code, Tag):
                classes = inner_code.get("class") or []
                for cls in classes:
                    if cls.startswith("language-"):
                        language = cls[len("language-") :]
                        break
            if code_text.strip():
                blocks.append(CodeBlock(kind="code", text=code_text, language=language))
            continue

        if name == "table":
            rows = _table_rows(descendant)
            if rows:
                blocks.append(TableBlock(kind="table", rows=rows))
            continue

        if name in BLOCK_LEVEL_TAGS:
            text = descendant.get_text(" ", strip=True)
            if text:
                emit_paragraph(text)
            continue

    if not blocks:
        # Fallback: flatten remaining text if structured walk produced nothing
        text = root.get_text("\n", strip=True)
        for line in text.splitlines():
            cleaned = _normalize_text(line)
            if cleaned:
                blocks.append(ParagraphBlock(kind="paragraph", text=cleaned))
    return blocks


def _flatten_blocks(blocks: list[Block]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    headings: list[str] = []
    for block in blocks:
        if block.kind == "heading":
            headings.append(block.text)
            text_parts.append(block.text)
        elif block.kind == "paragraph":
            text_parts.append(block.text)
        elif block.kind == "code":
            text_parts.append(block.text)
        elif block.kind == "table":
            for row in block.rows:
                text_parts.append(" | ".join(row))
    return "\n".join(text_parts), headings


def extract_page(url: str, html: str) -> ExtractedPage:
    soup = _make_soup(html)
    title = _title_from_soup(soup, url)
    _clean_soup(soup)
    root = _select_content_root(soup)
    blocks = _walk_blocks(root)
    text, headings = _flatten_blocks(blocks)
    if not headings:
        headings = [title] if title else []
    word_count = len(text.split())
    return ExtractedPage(
        url=url,
        title=title,
        headings=headings,
        text=text,
        word_count=word_count,
        blocks=blocks,
    )
