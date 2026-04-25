from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from app.core.constants import DEFAULT_USER_AGENT
from app.core.errors import FetchError


@dataclass(slots=True)
class SimpleResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        content_type = self.headers.get("content-type", "")
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.rsplit("charset=", 1)[-1].split(";", 1)[0].strip() or encoding
        return self.content.decode(encoding, errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FetchError(f"HTTP error {self.status_code}: {self.url}")


class SimpleHttpClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        self._opener = build_opener()

    def __enter__(self) -> "SimpleHttpClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def close(self) -> None:
        return None

    def get(self, url: str) -> SimpleResponse:
        request = Request(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                return SimpleResponse(url=response.geturl(), status_code=response.status, headers=headers, content=response.read())
        except HTTPError as exc:
            headers = {key.lower(): value for key, value in exc.headers.items()}
            return SimpleResponse(url=url, status_code=exc.code, headers=headers, content=exc.read())
        except URLError as exc:
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc


def create_http_client(timeout: int) -> SimpleHttpClient:
    return SimpleHttpClient(timeout)
