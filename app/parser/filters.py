from pathlib import PurePosixPath
from urllib.parse import urlparse

from app.config.models import ExportConfig
from app.core.constants import DEFAULT_SKIP_EXTENSIONS, DEFAULT_SKIP_KEYWORDS
from app.parser.urls import infer_path_prefix, is_same_domain, normalize_url


def should_skip_url(url: str, config: ExportConfig, *, require_prefix: bool = True) -> bool:
    normalized = normalize_url(url, config.url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return True
    if not is_same_domain(config.url, normalized):
        return True

    lower_path = parsed.path.lower()
    suffix = PurePosixPath(lower_path).suffix
    if suffix in DEFAULT_SKIP_EXTENSIONS:
        return True
    if any(keyword in lower_path for keyword in DEFAULT_SKIP_KEYWORDS):
        return True
    if require_prefix and not lower_path.startswith(infer_path_prefix(config.url).lower()):
        return True
    if config.include and not any(token in normalized for token in config.include):
        return True
    if config.exclude and any(token in normalized for token in config.exclude):
        return True
    return False


def deduplicate_and_filter(urls: list[str], config: ExportConfig, *, require_prefix: bool = True) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = normalize_url(url, config.url)
        if normalized in seen or should_skip_url(normalized, config, require_prefix=require_prefix):
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
