class Api2PdfError(Exception):
    """Base application error."""


class NoValidPageError(Api2PdfError):
    """Raised when no crawlable page is discovered."""


class FetchError(Api2PdfError):
    """Raised when a page cannot be fetched."""


class ExtractionError(Api2PdfError):
    """Raised when content extraction yields no useful text."""


class PdfExportError(Api2PdfError):
    """Raised when PDF generation fails."""
