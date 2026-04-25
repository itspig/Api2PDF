from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def remove_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def normalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url, url) if base_url else url
    parsed = urlparse(remove_fragment(absolute))
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    # Preserve trailing slash on directory-style URLs - some hosts hang on the
    # bare path, and the original semantics (directory vs. file) matter.
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key in TRACKING_QUERY_KEYS or key.startswith(TRACKING_QUERY_PREFIXES):
            continue
        query_pairs.append((key, value))
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_same_domain(base: str, target: str) -> bool:
    return urlparse(base).netloc.lower() == urlparse(target).netloc.lower()


def infer_path_prefix(url: str) -> str:
    path = urlparse(url).path or "/"
    if path.endswith("/"):
        return path
    parent = str(PurePosixPath(path).parent)
    if parent == ".":
        return "/"
    return parent.rstrip("/") + "/"


def root_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
