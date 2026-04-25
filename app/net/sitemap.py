from __future__ import annotations

from xml.etree import ElementTree

from app.config.models import ExportConfig
from app.parser.filters import deduplicate_and_filter
from app.parser.urls import root_url

MAX_SITEMAP_BYTES = 10 * 1024 * 1024


def discover_sitemaps(start_url: str, client) -> list[str]:
    site_root = root_url(start_url)
    candidates = [f"{site_root.rstrip('/')}/sitemap.xml", f"{site_root.rstrip('/')}/sitemap_index.xml"]
    robots_url = f"{site_root.rstrip('/')}/robots.txt"
    try:
        robots = client.get(robots_url)
        if robots.status_code == 200:
            for line in robots.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url:
                        candidates.append(sitemap_url)
    except Exception:
        pass
    return list(dict.fromkeys(candidates))


def _xml_namespace(root: ElementTree.Element) -> dict[str, str]:
    if root.tag.startswith("{"):
        uri = root.tag.split("}", 1)[0][1:]
        return {"sm": uri}
    return {}


def _find_texts(root: ElementTree.Element, tag: str) -> list[str]:
    namespace = _xml_namespace(root)
    if namespace:
        nodes = root.findall(f".//sm:{tag}", namespace)
    else:
        nodes = root.findall(f".//{tag}")
    return [node.text.strip() for node in nodes if node.text and node.text.strip()]


def parse_sitemap(url: str, client, *, depth: int = 0, max_depth: int = 3, limit: int | None = None) -> list[str]:
    if depth > max_depth or limit == 0:
        return []
    try:
        response = client.get(url)
        if response.status_code >= 400:
            return []
    except Exception:
        return []

    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_SITEMAP_BYTES:
                return []
        except ValueError:
            return []
    if len(response.content) > MAX_SITEMAP_BYTES:
        return []

    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError:
        return []

    tag_name = root.tag.rsplit("}", 1)[-1]
    if tag_name == "sitemapindex":
        urls: list[str] = []
        for child_sitemap in _find_texts(root, "loc"):
            remaining = None if limit is None else max(limit - len(urls), 0)
            if remaining == 0:
                break
            urls.extend(parse_sitemap(child_sitemap, client, depth=depth + 1, max_depth=max_depth, limit=remaining))
        return urls
    locs = _find_texts(root, "loc")
    return locs if limit is None else locs[:limit]


def discover_urls_from_sitemap(start_url: str, client, config: ExportConfig) -> list[str]:
    urls: list[str] = []
    for sitemap_url in discover_sitemaps(start_url, client):
        remaining = max(config.max_pages - len(urls), 0)
        if remaining == 0:
            break
        urls.extend(parse_sitemap(sitemap_url, client, limit=remaining))
        if len(urls) >= config.max_pages:
            break
    return deduplicate_and_filter(urls, config)
