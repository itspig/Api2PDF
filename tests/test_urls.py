from app.parser.urls import infer_path_prefix, is_same_domain, normalize_url, remove_fragment


def test_remove_fragment() -> None:
    assert remove_fragment("https://example.com/a#b") == "https://example.com/a"


def test_normalize_url_removes_tracking_and_keeps_trailing_slash() -> None:
    url = normalize_url("HTTPS://Example.COM/a/b/?utm_source=x&keep=1#section")
    assert url == "https://example.com/a/b/?keep=1"


def test_normalize_url_keeps_non_directory_path() -> None:
    url = normalize_url("HTTPS://Example.COM/a/b?keep=1")
    assert url == "https://example.com/a/b?keep=1"


def test_same_domain() -> None:
    assert is_same_domain("https://docs.example.com/a", "https://docs.example.com/b")
    assert not is_same_domain("https://docs.example.com/a", "https://api.example.com/b")


def test_infer_path_prefix() -> None:
    # File-style URL: prefix is the file's directory.
    assert infer_path_prefix("http://docs.thinktrader.net/pages/040ff7.html") == "/pages/"
    # Non-directory path: prefix is the inferred parent directory.
    assert infer_path_prefix("http://docs.thinktrader.net/pages/040ff7") == "/pages/"
    # Directory-style URL: step up so siblings under the parent are discovered.
    assert infer_path_prefix("http://docs.thinktrader.net/pages/040ff7/") == "/pages/"
    # First-level directory: cannot step above root, return itself.
    assert infer_path_prefix("https://example.com/docs/") == "/docs/"
    assert infer_path_prefix("https://example.com/") == "/"
