"""Fetchers for arXiv, IACR ePrint, and GitHub. stdlib only.

Each fetcher yields plain dicts (see store.Item); network access goes through
an injectable ``get(url) -> bytes`` so tests run offline against fixtures.
Callers pace requests (arXiv asks ~3s between calls; ePrint/GitHub be polite).
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

ARXIV_API = "https://export.arxiv.org/api/query"
EPRINT_RSS = "https://eprint.iacr.org/rss/rss.xml"
EPRINT_SEARCH = "https://eprint.iacr.org/search"
GITHUB_API = "https://api.github.com"


def http_get(url: str, user_agent: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _iso_day(value: str | None) -> str | None:
    """Best-effort normalize of assorted date formats to YYYY-MM-DD."""
    if not value:
        return None
    value = value.strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def _clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- arXiv


def arxiv_query_url(query: str, start: int, max_results: int) -> str:
    # Split into AND-ed terms (shlex keeps "quoted phrases" together);
    # a single quoted multi-word phrase would match almost nothing.
    import shlex
    try:
        terms = shlex.split(query)
    except ValueError:
        terms = [query]
    terms = [t for t in terms if t] or [query]
    expr = " AND ".join(f'all:"{t}"' if " " in t else f"all:{t}" for t in terms)
    params = {
        "search_query": expr,
        "start": str(start),
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return ARXIV_API + "?" + urllib.parse.urlencode(params)


def parse_arxiv_atom(data: bytes) -> tuple[list[dict], int]:
    """Parse one Atom page -> (items, total_results)."""
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(data)
    total_el = root.find("opensearch:totalResults", ns)
    total = int(total_el.text or 0) if total_el is not None else 0
    items = []
    for entry in root.findall("a:entry", ns):
        id_url = (entry.findtext("a:id", default="", namespaces=ns) or "").strip()
        m = re.search(r"arxiv\.org/abs/([^v]+)v?\d*$", id_url)
        ext_id = m.group(1) if m else id_url.rsplit("/", 1)[-1]
        items.append({
            "source": "arxiv",
            "ext_id": ext_id,
            "title": _clean(entry.findtext("a:title", default="", namespaces=ns)),
            "authors": [a.findtext("a:name", default="", namespaces=ns).strip()
                        for a in entry.findall("a:author", ns)],
            "url": f"https://arxiv.org/abs/{ext_id}",
            "published": _iso_day(entry.findtext("a:published", namespaces=ns)),
            "updated": _iso_day(entry.findtext("a:updated", namespaces=ns)),
            "abstract": _clean(entry.findtext("a:summary", default="", namespaces=ns)),
            "categories": [c.get("term", "") for c in entry.findall("a:category", ns)],
            "extra": {"pdf": f"https://arxiv.org/pdf/{ext_id}"},
        })
    return items, total


def fetch_arxiv(query: str, max_results: int, get) -> list[dict]:
    data = get(arxiv_query_url(query, 0, max_results))
    items, _ = parse_arxiv_atom(data)
    return items


# ---------------------------------------------------------------- ePrint


def parse_eprint_rss(data: bytes) -> list[dict]:
    ns = {"dc": "http://purl.org/dc/elements/1.1/"}
    root = ET.fromstring(data)
    items = []
    for it in root.find("channel").findall("item"):
        link = (it.findtext("link") or "").strip()
        m = re.search(r"eprint\.iacr\.org/(\d{4}/\d+)", link)
        if not m:
            continue
        cats = [c.text for c in it.findall("category") if c.text]
        creators = [c.text for c in it.findall("dc:creator", ns) if c.text]
        items.append({
            "source": "eprint",
            "ext_id": m.group(1),
            "title": _clean(it.findtext("title")),
            "authors": creators,
            "url": link,
            "published": _iso_day(it.findtext("pubDate")),
            "updated": None,
            "abstract": _clean(it.findtext("description")),
            "categories": cats,
            "extra": {},
        })
    return items


def fetch_eprint_rss(get) -> list[dict]:
    return parse_eprint_rss(get(EPRINT_RSS))


_BLOCK = re.compile(r'<div class="mb-4">(.*?)(?=<div class="mb-4">|\Z)', re.S)


def parse_eprint_search(html_text: str) -> list[dict]:
    """Parse one search-result page. Tolerant: blocks missing an id are skipped.

    Note: search-page abstracts are truncated by the site; the RSS abstract
    (when the same paper appears there) is fuller. Store keeps the longest.
    """
    items = []
    for block in _BLOCK.findall(html_text):
        m = re.search(r'class="paperlink" href="/(\d{4}/\d+)"', block)
        if not m:
            continue
        ext_id = m.group(1)
        title = re.search(r"<strong>(.*?)</strong>", block, re.S)
        authors = re.search(r'<span class="fst-italic">(.*?)</span>', block, re.S)
        cat = re.search(r'class="badge category[^"]*">(.*?)</small>', block, re.S)
        updated = re.search(r"Last updated:\s*([\d-]+)", block)
        abstract = re.search(r'class="[^"]*search-abstract">(.*?)</p>', block, re.S)
        auth_list = []
        if authors:
            auth_list = [a.strip() for a in re.split(r",\s*|\s+and\s+", _clean(authors.group(1)))
                         if a.strip()]
        items.append({
            "source": "eprint",
            "ext_id": ext_id,
            "title": _clean(title.group(1)) if title else ext_id,
            "authors": auth_list,
            "url": f"https://eprint.iacr.org/{ext_id}",
            "published": None,
            "updated": _iso_day(updated.group(1)) if updated else None,
            "abstract": _clean(abstract.group(1)) if abstract else "",
            "categories": [_clean(cat.group(1))] if cat else [],
            "extra": {},
        })
    return items


def fetch_eprint_search(query: str, pages: int, get) -> list[dict]:
    out: list[dict] = []
    for page in range(max(1, pages)):
        url = EPRINT_SEARCH + "?" + urllib.parse.urlencode(
            {"q": query, "offset": str(page * 100)})
        data = get(url)
        found = parse_eprint_search(data.decode("utf-8", "replace"))
        out.extend(found)
        if len(found) < 100:
            break
    return out


# ---------------------------------------------------------------- GitHub


def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def github_get(path: str, user_agent: str, timeout: float = 30.0) -> bytes:
    """GET api.github.com path with optional token auth + rate-limit errors."""
    req = urllib.request.Request(
        GITHUB_API + path,
        headers={"User-Agent": user_agent, "Accept": "application/vnd.github+json"},
    )
    token = _github_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:  # noqa: BLE001 -- surface rate limits
        if exc.code == 403:
            reset = exc.headers.get("X-RateLimit-Reset", "?")
            raise RuntimeError(f"GitHub rate limited; resets at epoch {reset}") from exc
        raise


def github_search_repos(query: str, since: str, min_stars: int, max_results: int,
                        get) -> list[dict]:
    """Search repositories created since YYYY-MM-DD with a star floor."""
    q = f"{query} created:>{since} stars:>={min_stars}"
    params = urllib.parse.urlencode(
        {"q": q, "sort": "stars", "order": "desc", "per_page": str(min(max_results, 100))})
    data = json.loads(get(f"/search/repositories?{params}"))
    items = []
    for r in data.get("items", []):
        items.append({
            "source": "github",
            "ext_id": f"repo:{r['full_name']}",
            "title": r["full_name"],
            "authors": [r["owner"]["login"]] if r.get("owner") else [],
            "url": r["html_url"],
            "published": _iso_day(r.get("created_at")),
            "updated": _iso_day(r.get("pushed_at")),
            "abstract": r.get("description") or "",
            "categories": (r.get("topics") or []),
            "extra": {"stars": r.get("stargazers_count", 0),
                      "language": r.get("language") or "",
                      "kind": "repo"},
        })
    return items


def github_repo_releases(owner_repo: str, get, max_results: int = 5) -> list[dict]:
    data = json.loads(get(f"/repos/{owner_repo}/releases?per_page={max_results}"))
    items = []
    for r in (data or [])[:max_results]:
        items.append({
            "source": "github",
            "ext_id": f"release:{owner_repo}@{r.get('tag_name')}",
            "title": f"{owner_repo} {r.get('name') or r.get('tag_name')}",
            "authors": [r["author"]["login"]] if r.get("author") else [],
            "url": r.get("html_url", ""),
            "published": _iso_day(r.get("published_at")),
            "updated": None,
            "abstract": (r.get("body") or "")[:2000],
            "categories": [],
            "extra": {"kind": "release", "tag": r.get("tag_name")},
        })
    return items


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def days_ago_iso(n: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc).date() - timedelta(days=n)).isoformat()


def within_days(iso_day: str | None, n: int) -> bool:
    if not iso_day:
        return True  # unknown date: keep, rank lower instead of dropping
    try:
        d = date.fromisoformat(iso_day)
    except ValueError:
        return True
    return (date.today() - d).days <= n
