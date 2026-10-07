"""Parser tests: fixed fixtures, no network."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from litwatch import sources  # noqa: E402

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>2</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2610.06783v1</id>
    <title>Truly Subquadratic 3SUM</title>
    <author><name>Josh Alman</name></author>
    <author><name>Virginia Vassilevska Williams</name></author>
    <published>2026-10-05T00:00:00Z</published>
    <updated>2026-10-06T00:00:00Z</updated>
    <summary>We give O(n^1.9992) 3SUM.</summary>
    <category term="cs.DS"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/1234.5678v2</id>
    <title>Other</title>
    <published>2026-01-01T00:00:00Z</published>
    <summary>x</summary>
  </entry>
</feed>
"""

RSS = b"""<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0"><channel>
<item><title>Index Calculus on Sieves</title>
<link>https://eprint.iacr.org/2026/1234</link>
<description><![CDATA[An <b>abstract</b> here.]]></description>
<category>Public-key cryptography</category>
<pubDate>Tue, 06 Oct 2026 04:33:46 +0000</pubDate>
<dc:creator>Ada Lovelace</dc:creator></item>
<item><title>Not a paper</title><link>https://example.com/</link></item>
</channel></rss>
"""

SEARCH_HTML = """
<div class="ms-lg-4 mt-3 results">
  <div class="mb-4">
    <div class="d-flex"><a title="2026/2327" class="paperlink" href="/2026/2327">2026/2327</a>
      <small class="ms-auto">Last updated: 2026-10-04</small>
    </div>
    <div class="ms-md-4"><div>
      <strong>Humbert Form Paper</strong>
      <div class="mt-1"><span class="fst-italic">Tony Shaska and Ada Lovelace</span></div>
    </div>
    <small class="badge category category-PUBLICKEY">Public-key cryptography</small>
    <p class="mb-0 mt-1 search-abstract">An abstract that trails off whose every...</p>
    </div>
  </div>
  <div class="mb-4"><div class="d-flex">no paperlink here</div></div>
</div>
"""

GH_REPOS = {
    "items": [{
        "full_name": "openai/math",
        "owner": {"login": "openai"},
        "html_url": "https://github.com/openai/math",
        "created_at": "2026-10-06T21:47:02Z",
        "pushed_at": "2026-10-06T22:01:11Z",
        "description": "math manuscripts",
        "topics": ["lean4"],
        "stargazers_count": 42,
        "language": "Lean",
    }]
}

GH_RELEASES = [{
    "tag_name": "v1.0", "name": "First",
    "author": {"login": "octo"},
    "html_url": "https://github.com/o/r/releases/v1",
    "published_at": "2026-10-01T00:00:00Z",
    "body": "notes",
}]


class ArxivTests(unittest.TestCase):
    def test_entries_and_version_stripping(self):
        items, total = sources.parse_arxiv_atom(ATOM)
        self.assertEqual(total, 2)
        self.assertEqual(items[0]["ext_id"], "2610.06783")
        self.assertEqual(items[0]["authors"], ["Josh Alman", "Virginia Vassilevska Williams"])
        self.assertEqual(items[0]["published"], "2026-10-05")
        self.assertEqual(items[0]["categories"], ["cs.DS"])
        self.assertEqual(items[0]["url"], "https://arxiv.org/abs/2610.06783")
        self.assertEqual(items[1]["ext_id"], "1234.5678")

    def test_query_url_shape(self):
        url = sources.arxiv_query_url("3SUM", 0, 5)
        self.assertIn("export.arxiv.org/api/query", url)
        self.assertIn("sortBy=submittedDate", url)
        self.assertIn("3SUM", url)


class EprintTests(unittest.TestCase):
    def test_rss_items_and_nonpaper_skip(self):
        items = sources.parse_eprint_rss(RSS)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["ext_id"], "2026/1234")
        self.assertEqual(it["authors"], ["Ada Lovelace"])
        self.assertEqual(it["published"], "2026-10-06")
        self.assertEqual(it["abstract"], "An abstract here.")
        self.assertEqual(it["categories"], ["Public-key cryptography"])

    def test_search_blocks_and_skip(self):
        items = sources.parse_eprint_search(SEARCH_HTML)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["ext_id"], "2026/2327")
        self.assertEqual(it["title"], "Humbert Form Paper")
        self.assertEqual(it["authors"], ["Tony Shaska", "Ada Lovelace"])
        self.assertEqual(it["updated"], "2026-10-04")
        self.assertIn("trails off", it["abstract"])

    def test_search_pagination_stops_short(self):
        calls = []

        def get(url):
            calls.append(url)
            return SEARCH_HTML.encode()
        out = sources.fetch_eprint_search("x", 3, get)
        self.assertEqual(len(out), 1)  # <100 results -> stops after page 1
        self.assertEqual(len(calls), 1)


class GithubTests(unittest.TestCase):
    def test_repo_items(self):
        out = sources.github_search_repos("q", "2026-10-01", 5, 10,
                                          lambda url: json.dumps(GH_REPOS).encode())
        self.assertEqual(len(out), 1)
        it = out[0]
        self.assertEqual(it["ext_id"], "repo:openai/math")
        self.assertEqual(it["published"], "2026-10-06")
        self.assertEqual(it["extra"]["stars"], 42)

    def test_release_items(self):
        out = sources.github_repo_releases(
            "o/r", lambda url: json.dumps(GH_RELEASES).encode())
        self.assertEqual(out[0]["ext_id"], "release:o/r@v1.0")
        self.assertEqual(out[0]["published"], "2026-10-01")


class DateTests(unittest.TestCase):
    def test_iso_day_formats(self):
        self.assertEqual(sources._iso_day("2026-10-05T00:00:00Z"), "2026-10-05")
        self.assertEqual(sources._iso_day("Tue, 06 Oct 2026 04:33:46 +0000"), "2026-10-06")
        self.assertIsNone(sources._iso_day(None))
        self.assertIsNone(sources._iso_day(""))

    def test_within_days_unknown_kept(self):
        self.assertTrue(sources.within_days(None, 7))
        self.assertTrue(sources.within_days("not-a-date", 7))


if __name__ == "__main__":
    unittest.main()
