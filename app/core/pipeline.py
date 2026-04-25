from urllib.parse import urlparse, urljoin
import re
import sys
from html.parser import HTMLParser
from collections import deque

from app.config.models import ExportConfig
from app.core.errors import ExtractionError, NoValidPageError
from app.document.models import (
    Block,
    CodeBlock,
    ExtractedPage,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
)
from app.utils.file_utils import resolve_output_path


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http(s) URL")


def create_client(timeout: int):
    from app.net.client import create_http_client

    return create_http_client(timeout)


_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_PARAGRAPH_TAGS = {"p", "li", "blockquote", "dt", "dd"}
_SKIP_TAGS = {"script", "style", "nav", "footer", "aside", "noscript", "svg", "form", "header"}


class _StructuredExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[Block] = []
        self._title_buffer: list[str] = []
        self._in_title = False
        self._skip_depth = 0

        self._heading_stack: list[tuple[int, list[str]]] = []
        self._paragraph_stack: list[list[str]] = []
        self._pre_stack: list[list[str]] = []
        self._pre_language: str = ""

        self._table_stack: list[list[list[str]]] = []
        self._row_stack: list[list[str]] = []
        self._cell_stack: list[list[str]] = []

    def _attr_class(self, attrs: list[tuple[str, str | None]]) -> str:
        for key, value in attrs:
            if key.lower() == "class" and value:
                return value
        return ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower == "title":
            self._in_title = True
            return
        if lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return

        if lower in _HEADING_TAGS:
            self._heading_stack.append((int(lower[1]), []))
            return
        if lower == "pre":
            self._pre_stack.append([])
            self._pre_language = ""
            return
        if lower == "code" and self._pre_stack:
            classes = self._attr_class(attrs).split()
            for cls in classes:
                if cls.startswith("language-"):
                    self._pre_language = cls[len("language-") :]
                    break
            return
        if lower == "table":
            self._table_stack.append([])
            return
        if lower == "tr" and self._table_stack:
            self._row_stack.append([])
            return
        if lower in {"th", "td"} and self._row_stack:
            self._cell_stack.append([])
            return
        if lower in _PARAGRAPH_TAGS:
            self._paragraph_stack.append([])
            return
        if lower == "br":
            if self._pre_stack:
                self._pre_stack[-1].append("\n")
            elif self._cell_stack:
                self._cell_stack[-1].append(" ")
            elif self._paragraph_stack:
                self._paragraph_stack[-1].append(" ")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title":
            self.title = " ".join("".join(self._title_buffer).split())
            self._title_buffer = []
            self._in_title = False
            return
        if lower in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return

        if lower in _HEADING_TAGS and self._heading_stack:
            level, parts = self._heading_stack.pop()
            text = " ".join("".join(parts).split())
            if text:
                self.blocks.append(HeadingBlock(kind="heading", level=level, text=text))
            return
        if lower == "pre" and self._pre_stack:
            parts = self._pre_stack.pop()
            text = "".join(parts).strip("\n")
            if text.strip():
                self.blocks.append(CodeBlock(kind="code", text=text, language=self._pre_language))
            self._pre_language = ""
            return
        if lower == "table" and self._table_stack:
            rows = self._table_stack.pop()
            if rows:
                self.blocks.append(TableBlock(kind="table", rows=rows))
            return
        if lower == "tr" and self._row_stack:
            row = self._row_stack.pop()
            if row and self._table_stack:
                self._table_stack[-1].append(row)
            return
        if lower in {"th", "td"} and self._cell_stack:
            cell_text = " ".join("".join(self._cell_stack.pop()).split())
            if self._row_stack:
                self._row_stack[-1].append(cell_text)
            return
        if lower in _PARAGRAPH_TAGS and self._paragraph_stack:
            parts = self._paragraph_stack.pop()
            text = " ".join("".join(parts).split())
            if text:
                self.blocks.append(ParagraphBlock(kind="paragraph", text=text))
            return

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buffer.append(data)
            return
        if self._skip_depth:
            return
        if self._pre_stack:
            self._pre_stack[-1].append(data)
            return
        if self._cell_stack:
            self._cell_stack[-1].append(data)
            return
        if self._heading_stack:
            self._heading_stack[-1][1].append(data)
            return
        if self._paragraph_stack:
            self._paragraph_stack[-1].append(data)


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


def _extract_page_stdlib(url: str, html: str) -> ExtractedPage:
    parser = _StructuredExtractor()
    parser.feed(html)
    blocks = parser.blocks
    text, headings = _flatten_blocks(blocks)
    title = parser.title or url
    if not headings:
        headings = [title] if title else []
    return ExtractedPage(
        url=url,
        title=title,
        headings=headings,
        text=text,
        word_count=len(text.split()),
        blocks=blocks,
    )


class _StdlibLinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


def _extract_links_stdlib(html: str) -> list[str]:
    parser = _StdlibLinkExtractor()
    parser.feed(html)
    return parser.links


def _crawl_site_stdlib(start_url: str, config: ExportConfig, client) -> list[str]:
    from app.net.fetcher import fetch
    from app.parser.filters import should_skip_url
    from app.parser.urls import normalize_url

    start = normalize_url(start_url)
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    seen: set[str] = set()
    ordered: list[str] = []

    while queue and len(ordered) < config.max_pages:
        url, depth = queue.popleft()
        normalized = normalize_url(url, config.url)
        if normalized in seen or should_skip_url(normalized, config):
            continue
        seen.add(normalized)
        try:
            result = fetch(client, normalized)
        except Exception as exc:
            if config.debug:
                print(f"crawl: fetch failed for {normalized}: {exc}", flush=True)
            continue
        if result.content_type and "html" not in result.content_type:
            if config.debug:
                print(f"crawl: skipping non-html {normalized} ({result.content_type})", flush=True)
            continue
        ordered.append(normalize_url(result.final_url))
        if config.debug:
            print(f"crawl: visited {normalized} (depth {depth})", flush=True)
        if depth >= config.max_depth:
            continue
        for link in _extract_links_stdlib(result.text):
            next_url = normalize_url(urljoin(result.final_url, link), result.final_url)
            if next_url not in seen and not should_skip_url(next_url, config):
                queue.append((next_url, depth + 1))

    return ordered


def run_export(config: ExportConfig) -> str:
    from app.document.compiler import compile_document
    from app.net.fetcher import fetch_html
    from app.net.sitemap import discover_urls_from_sitemap
    if getattr(sys, "frozen", False):
        extract_page = _extract_page_stdlib
        crawl_site = _crawl_site_stdlib
    else:
        from app.net.crawler import crawl_site
        from app.parser.extractor import extract_page
    from app.parser.filters import deduplicate_and_filter
    from app.utils.logger import info, success, warning

    config.validate()
    validate_url(config.url)
    output_path = resolve_output_path(config.url, config.output)

    with create_client(config.timeout) as client:
        urls: list[str] = []
        if not config.no_sitemap:
            info("Discovering URLs from sitemap...")
            urls = discover_urls_from_sitemap(config.url, client, config)
        if not urls:
            warning("No sitemap URLs found. Falling back to BFS crawl...")
            if config.debug:
                print("crawl: starting", flush=True)
            urls = crawl_site(config.url, config, client)
            if config.debug:
                print(f"crawl: returned {len(urls)} urls", flush=True)

        if config.debug:
            print("filter: deduplicating", flush=True)
        urls = deduplicate_and_filter(urls, config)[: config.max_pages]
        if config.debug:
            print(f"filter: {len(urls)} urls after filter", flush=True)
        if not urls:
            raise NoValidPageError("No crawlable documentation pages were found.")

        extracted_pages: list[ExtractedPage] = []
        for index, url in enumerate(urls, start=1):
            if config.debug:
                print(f"[{index}/{len(urls)}] Fetching {url}", flush=True)
            try:
                html = fetch_html(client, url)
                page = extract_page(url, html)
            except Exception as exc:
                if config.debug:
                    print(f"Skipping {url}: {exc}", flush=True)
                continue
            if page.text.strip():
                extracted_pages.append(page)
            if config.debug:
                print(f"  extracted {page.word_count} words", flush=True)

    if not extracted_pages:
        raise ExtractionError("No readable content extracted from any page.")

    document = compile_document(config.url, extracted_pages)
    from app.exporter.pdf_exporter import export_pdf

    export_pdf(document, output_path)
    success(f"Exported {len(extracted_pages)} pages to {output_path}")
    return output_path
