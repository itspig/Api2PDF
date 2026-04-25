from urllib.parse import urlparse

from app.document.models import CompiledDocument, ExtractedPage
from app.document.sorter import sort_pages
from app.utils.time_utils import utc_now_iso


def compile_document(source_url: str, pages: list[ExtractedPage]) -> CompiledDocument:
    host = urlparse(source_url).netloc or source_url
    sorted_pages = sort_pages(pages)
    return CompiledDocument(
        site_title=f"API Documentation - {host}",
        source_url=source_url,
        generated_at=utc_now_iso(),
        pages=sorted_pages,
    )
