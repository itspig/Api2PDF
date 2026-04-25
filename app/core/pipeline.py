from urllib.parse import urlparse
import re
import sys
from html.parser import HTMLParser
from collections import deque
from urllib.parse import urljoin

from app.config.models import ExportConfig
from app.core.errors import ExtractionError, NoValidPageError
from app.document.models import ExtractedPage
from app.utils.file_utils import resolve_output_path


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute http(s) URL")


def create_client(timeout: int):
    from app.net.client import create_http_client

    return create_http_client(timeout)


class _PlainTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.headings: list[str] = []
        self._skip_depth = 0
        self._current_tag = ""
        self._buffer: list[str] = []
        self._title_buffer: list[str] = []
        self._heading_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        self._current_tag = lower
        if lower in {"script", "style", "nav", "footer", "aside", "noscript", "svg"}:
            self._skip_depth += 1
        if lower in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self._buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style", "nav", "footer", "aside", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if lower == "title" and not self.title:
            self.title = " ".join("".join(self._title_buffer).split())
            self._title_buffer = []
        if lower in {"h1", "h2", "h3"}:
            heading = " ".join("".join(self._heading_buffer).split())
            if heading:
                self.headings.append(heading)
                if not self.title:
                    self.title = heading
            self._heading_buffer = []
        self._current_tag = ""

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current_tag == "title":
            self._title_buffer.append(data)
        if self._current_tag in {"h1", "h2", "h3"}:
            self._heading_buffer.append(data)
        self._buffer.append(data)

    def text(self) -> str:
        raw = "".join(self._buffer)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def _extract_page_stdlib(url: str, html: str) -> ExtractedPage:
    parser = _PlainTextExtractor()
    parser.feed(html)
    text = parser.text()
    title = parser.title or url
    headings = parser.headings or [title]
    return ExtractedPage(url=url, title=title, headings=headings, text=text, word_count=len(text.split()))


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
