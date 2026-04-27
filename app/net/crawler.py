from collections import deque

from app.config.models import ExportConfig


def crawl_site(start_url: str, config: ExportConfig, client) -> list[str]:
    from app.net.fetcher import fetch
    from app.parser.filters import should_follow_link, should_skip_url
    from app.parser.html_parser import extract_links
    from app.parser.urls import normalize_url

    start = normalize_url(start_url)
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    seen: set[str] = set()
    ordered: list[str] = []

    while queue and len(ordered) < config.max_pages:
        url, depth = queue.popleft()
        normalized = normalize_url(url, config.url)
        if normalized in seen or should_skip_url(normalized, config):
            continue
        seen.add(normalized)
        try:
            result = fetch(client, normalized)
        except Exception as exc:
            if config.debug:
                print(f"crawl: fetch failed for {normalized}: {exc}", flush=True)
            continue
        if result.content_type and "html" not in result.content_type:
            if config.debug:
                print(f"crawl: skipping non-html {normalized} ({result.content_type})", flush=True)
            continue
        ordered.append(normalize_url(result.final_url))
        if config.debug:
            print(f"crawl: visited {normalized} (depth {depth})", flush=True)
        if depth >= config.max_depth:
            continue
        for link in extract_links(result.text, result.final_url):
            next_url = normalize_url(link, result.final_url)
            if next_url not in seen and not should_skip_url(next_url, config) and should_follow_link(next_url, config):
                queue.append((next_url, depth + 1))

    return ordered
