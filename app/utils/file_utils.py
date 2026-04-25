from pathlib import Path
from urllib.parse import urlparse


def safe_filename_from_url(url: str, suffix: str = ".pdf") -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace(":", "_") or "document"
    path = parsed.path.strip("/").replace("/", "_")
    stem = f"{host}_{path}" if path else host
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in stem)
    return f"{safe}{suffix}"


def resolve_output_path(url: str, output: str | None) -> str:
    if output:
        return str(Path(output))
    return str(Path.cwd() / safe_filename_from_url(url))
