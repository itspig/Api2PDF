# Some sites drop or throttle non-browser User-Agents at the TLS/HTTP layer
# (observed on khsci.com, where our previous UA caused a TLS handshake timeout).
# We now default to a realistic Chrome on Windows UA so api2pdf works against
# such hosts out of the box.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

HTML_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
)

TEXT_LIKE_CONTENT_TYPES = HTML_CONTENT_TYPES + (
    "text/plain",
    "application/xml",
    "text/xml",
)

DEFAULT_SKIP_EXTENSIONS = {
    ".js",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".mp3",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

DEFAULT_SKIP_KEYWORDS = (
    # Auth and account flows
    "login",
    "signin",
    "signup",
    "register",
    "logout",
    "password",
    "lostpassword",
    # Site-search and filtered listings (rarely useful as docs)
    "search",
    "tag",
    "category",
    # Static asset directories that are sometimes served as routable HTML
    "assets",
    "static",
    "download",
    "attachment",
    # Common WordPress non-content paths that pollute BFS but never hold docs
    "wp-login",
    "wp-admin",
    "wp-json",
    "wp-content/uploads",
    "wp-content/plugins",
    "wp-content/themes",
    "wp-includes",
)


# Query parameter names whose mere presence marks a URL as auxiliary (login
# redirects, post-action endpoints, share dialogs, etc.). We skip URLs that
# carry any of them.
DEFAULT_SKIP_QUERY_KEYS = (
    "redirect_to",
    "action",
    "_wpnonce",
    "share",
    "replytocom",
)

DOCUMENT_SELECTORS = [
    "article",
    "main",
    ".markdown-body",
    ".content",
    ".doc-content",
    ".theme-default-content",
    ".vp-doc",
    ".rst-content",
    ".post-content",
]
