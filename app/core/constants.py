DEFAULT_USER_AGENT = "api2pdf/0.1 (+https://example.invalid/api2pdf)"

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
    "login",
    "signin",
    "signup",
    "search",
    "tag",
    "category",
    "assets",
    "static",
    "download",
    "attachment",
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
