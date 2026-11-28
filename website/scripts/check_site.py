"""Check built website links and fragments without contacting external services."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

SITE = "https://shrek-abaper.github.io"
BASE = "/sap-watt/"
DIST = Path(__file__).resolve().parents[1] / "dist"


class Page(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.ids = set()
        self.links = []
        self.feed(filename.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if "href" in attrs and attrs.get("rel") != "canonical":
            self.links.append(attrs["href"])
        if tag in {"img", "script", "source"} and "src" in attrs:
            self.links.append(attrs["src"])


def main():
    files = sorted(DIST.rglob("*.html"))
    if not files:
        raise SystemExit("No built pages found. Run npm run build first.")
    pages = {file: Page(file) for file in files}
    errors = []
    checked = 0
    for filename, page in pages.items():
        relative = filename.relative_to(DIST).as_posix()
        page_url = SITE + BASE + relative.removesuffix("index.html")
        for link in page.links:
            url = urlsplit(urljoin(page_url, link))
            if url.scheme not in {"https", "http"} or url.netloc != urlsplit(SITE).netloc:
                continue
            checked += 1
            if not url.path.startswith(BASE):
                errors.append(f"{relative}: missing project base: {link}")
                continue
            target = DIST / unquote(url.path.removeprefix(BASE))
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{relative}: missing target: {link}")
            elif url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids:
                errors.append(f"{relative}: missing fragment: {link}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(files)} pages and {checked} internal links/assets; no broken targets or fragments.")


if __name__ == "__main__":
    main()
