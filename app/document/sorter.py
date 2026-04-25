from app.document.models import ExtractedPage
from app.parser.urls import normalize_url


def sort_pages(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    seen: set[str] = set()
    unique: list[ExtractedPage] = []
    for page in pages:
        key = normalize_url(page.url)
        if key in seen or not page.text.strip():
            continue
        seen.add(key)
        unique.append(page)
    return unique
