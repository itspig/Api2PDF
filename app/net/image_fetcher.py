"""Best-effort image fetcher used by the export pipeline.

We download each unique ``ImageBlock.src`` once and cache the bytes in-memory.
Failures are swallowed: a missing image shows as a small "[image]" placeholder
in the PDF rather than aborting the whole export.

Defensive choices:
  * Limit per-image size (default 6 MB) so a stray giant asset cannot blow up
    the PDF or our memory budget.
  * Skip data: URIs and SVG (we can't render SVG without extra deps).
  * Use the same browser-like UA as the rest of the crawler so hosts that
    block non-browser requests still serve images.
  * Validate via Pillow when available so we never hand reportlab a payload
    that cannot decode.
"""

from __future__ import annotations

from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.core.constants import DEFAULT_USER_AGENT
from app.document.models import ImageBlock


def _ascii_safe(url: str) -> str:
    """Percent-encode the path/query so urllib doesn't choke on non-ASCII."""

    parts = urlsplit(url)
    safe_path = quote(parts.path, safe="/%:@!$&'()*+,;=~-._")
    safe_query = quote(parts.query, safe="=&%-._~")
    return urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))


_MAX_BYTES = 6 * 1024 * 1024
_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _is_supported_payload(data: bytes, mime_type: str) -> bool:
    if not data:
        return False
    if mime_type and "svg" in mime_type:
        return False
    try:
        from PIL import Image as PILImage  # type: ignore

        with PILImage.open(BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:
        # If Pillow isn't available or chokes, only trust common magic bytes.
        prefix = data[:8]
        return (
            prefix.startswith(b"\xff\xd8\xff")  # JPEG
            or prefix.startswith(b"\x89PNG\r\n\x1a\n")
            or prefix.startswith(b"GIF87a")
            or prefix.startswith(b"GIF89a")
            or prefix.startswith(b"BM")  # BMP
        )


def fetch_images(blocks_with_pages, *, timeout: int = 20, debug: bool = False) -> int:
    """Fill ``ImageBlock.data`` for each ``ImageBlock`` in ``blocks_with_pages``.

    ``blocks_with_pages`` is any iterable yielding ``ImageBlock`` objects
    (typically obtained by walking ``page.blocks`` for every page in the
    compiled document). Returns the number of images successfully populated.
    """

    cache: dict[str, tuple[bytes, str] | None] = {}
    populated = 0
    for block in blocks_with_pages:
        if not isinstance(block, ImageBlock) or block.data is not None:
            continue
        src = block.src
        if not src or src.lower().startswith("data:"):
            continue
        cached = cache.get(src)
        if cached is None and src not in cache:
            cached = _download(src, timeout=timeout, debug=debug)
            cache[src] = cached
        if cached is None:
            continue
        data, mime_type = cached
        block.data = data
        block.mime_type = mime_type
        populated += 1
    return populated


def _download(url: str, *, timeout: int, debug: bool) -> tuple[bytes, str] | None:
    try:
        request = Request(_ascii_safe(url), headers=_HEADERS)
        with urlopen(request, timeout=timeout) as response:
            mime_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > _MAX_BYTES:
                        if debug:
                            print(f"image: skip {url} (too large: {content_length} bytes)", flush=True)
                        return None
                except ValueError:
                    pass
            data = response.read(_MAX_BYTES + 1)
            if len(data) > _MAX_BYTES:
                if debug:
                    print(f"image: skip {url} (over {_MAX_BYTES} bytes)", flush=True)
                return None
            if not _is_supported_payload(data, mime_type):
                if debug:
                    print(f"image: skip {url} (unsupported payload, ct={mime_type})", flush=True)
                return None
            return data, mime_type
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        if debug:
            print(f"image: fetch failed {url}: {exc}", flush=True)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        if debug:
            print(f"image: unexpected error {url}: {exc}", flush=True)
        return None
