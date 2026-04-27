from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlparse

from app.config.models import ExportConfig
from app.core.constants import (
    DEFAULT_SKIP_EXTENSIONS,
    DEFAULT_SKIP_KEYWORDS,
    DEFAULT_SKIP_QUERY_KEYS,
)
from app.parser.urls import infer_path_prefix, is_same_domain, normalize_url

# Site-specific path prefixes that are ALWAYS allowed to be followed by the
# BFS even when the inferred crawl prefix would normally exclude them. This
# prevents a deep BFS from wandering into forum / admin / blog sections on
# documentation-heavy sites like khsci.com where the homepage links to
# everything at once.
_FOLLOW_PREFIXES_BY_HOST: dict[str, list[str]] = {
    "khsci.com": [
        "/khQuant/chapter",
        "/khQuant/tutor",
        "/khQuant/cli",
        "/khQuant/custind",
        "/khQuant/t0",
        "/khQuant/log",
        "/khQuant/qa",
        "/khQuant/prompt",
        "/khQuant/tutorial/",
        "/khQuant/3-3-",
    ],
}


def should_follow_link(url: str, config: ExportConfig) -> bool:
    """Decide whether the BFS crawler should enqueue ``url`` at depth >= 1.

    This is intentionally *more restrictive* than ``should_skip_url`` for
    site-specific domains: even though ``/khQuant/forum/`` is under the
    inferred crawl prefix, the BFS should not follow it because it leads to
    infinite forum threads.  The function returns ``True`` for generic hosts
    where no site-specific rules apply.
    """

    normalized = normalize_url(url, config.url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not is_same_domain(config.url, normalized):
        return False

    host = parsed.netloc.lower().split(":")[0]
    prefixes = _FOLLOW_PREFIXES_BY_HOST.get(host)
    if not prefixes:
        # Generic host: apply the normal skip logic only.
        return not should_skip_url(normalized, config)

    lower_path = parsed.path.lower()
    for prefix in prefixes:
        if lower_path.startswith(prefix.lower()):
            return True
    # Reject paths that don't match any allow-listed prefix on this host.
    return False


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
    if parsed.query:
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        if query_keys & set(DEFAULT_SKIP_QUERY_KEYS):
            return True
    if require_prefix:
        prefix = infer_path_prefix(config.url).lower()
        candidate = lower_path if lower_path.endswith("/") else lower_path + "/"
        if not (lower_path.startswith(prefix) or candidate == prefix):
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
