from dataclasses import dataclass

from app.core.constants import HTML_CONTENT_TYPES
from app.core.errors import FetchError


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str


def fetch(client, url: str) -> FetchResult:
    try:
        response = client.get(url)
        response.raise_for_status()
    except Exception as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc
    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    return FetchResult(
        url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=content_type,
        text=response.text,
    )


def fetch_html(client, url: str) -> str:
    result = fetch(client, url)
    if result.content_type and result.content_type not in HTML_CONTENT_TYPES:
        raise FetchError(f"URL is not HTML: {url} ({result.content_type})")
    return result.text
