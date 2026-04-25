from bs4 import BeautifulSoup, Tag

from app.core.constants import DOCUMENT_SELECTORS
from app.document.models import ExtractedPage


def _make_soup(html: str):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "lxml")


def _title_from_soup(soup: BeautifulSoup, url: str) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    return url


def _clean_soup(soup) -> None:
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside", "noscript", "svg"]):
        tag.decompose()


def _selector_text(soup) -> tuple[str, list[str]]:
    from bs4 import Tag

    for selector in DOCUMENT_SELECTORS:
        selected = soup.select_one(selector)
        if isinstance(selected, Tag):
            text = selected.get_text("\n", strip=True)
            if len(text) >= 80:
                headings = [h.get_text(" ", strip=True) for h in selected.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
                return text, headings
    return "", []


def _trafilatura_text(html: str) -> str:
    try:
        import trafilatura
    except ImportError:
        return ""
    extracted = trafilatura.extract(html, include_links=False, include_images=False)
    return extracted or ""


def _body_text(soup: BeautifulSoup) -> tuple[str, list[str]]:
    body = soup.body or soup
    text = body.get_text("\n", strip=True)
    headings = [h.get_text(" ", strip=True) for h in body.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
    return text, headings


def extract_page(url: str, html: str) -> ExtractedPage:
    soup = _make_soup(html)
    title = _title_from_soup(soup, url)
    _clean_soup(soup)

    text, headings = _selector_text(soup)
    if not text:
        text = _trafilatura_text(html)
    if not text:
        text, headings = _body_text(soup)

    cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(cleaned_lines)
    word_count = len(cleaned.split())
    if not headings:
        headings = [title] if title else []
    return ExtractedPage(url=url, title=title, headings=headings, text=cleaned, word_count=word_count)
