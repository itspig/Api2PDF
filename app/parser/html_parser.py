from bs4 import BeautifulSoup


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def extract_links(html: str, base_url: str) -> list[str]:
    soup = make_soup(html)
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if href:
            links.append(href)
    return links
