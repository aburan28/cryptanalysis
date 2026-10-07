"""Store, rank, config, and report tests (offline)."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from litwatch import config as config_mod  # noqa: E402
from litwatch import rank as rank_mod  # noqa: E402
from litwatch import report as report_mod  # noqa: E402
from litwatch import store as store_mod  # noqa: E402


def item(**kw):
    d = {"source": "arxiv", "ext_id": "1", "title": "t", "authors": [],
         "url": "u", "published": None, "updated": None, "abstract": "",
         "categories": [], "extra": {}}
    d.update(kw)
    return d


class StoreTests(unittest.TestCase):
    def test_upsert_new_then_refresh_keeps_longest_abstract(self):
        db = store_mod.connect(":memory:")
        self.assertTrue(store_mod.upsert(db, item(abstract="short")))
        self.assertFalse(store_mod.upsert(
            db, item(abstract="a much longer abstract here", categories=["x"])))
        got = store_mod.get(db, "arxiv", "1")
        self.assertEqual(got["abstract"], "a much longer abstract here")
        self.assertEqual(got["categories"], ["x"])
        # A shorter refresh must not clobber the longer abstract.
        self.assertFalse(store_mod.upsert(db, item(abstract="tiny")))
        self.assertEqual(store_mod.get(db, "arxiv", "1")["abstract"],
                         "a much longer abstract here")

    def test_scores_roundtrip(self):
        db = store_mod.connect(":memory:")
        store_mod.upsert(db, item())
        run = store_mod.start_run(db, "{}")
        store_mod.save_scores(db, run, [(item(), 9.5, "candidate", ["fine-grained"])])
        rows = db.execute("SELECT score, tier, topics FROM scores").fetchall()
        self.assertEqual(rows, [(9.5, "candidate", '["fine-grained"]')])


class RankTests(unittest.TestCase):
    def setUp(self):
        self.topics = [config_mod.Topic("fine-grained", 3.0, ["3SUM", "subquadratic"]),
                       config_mod.Topic("other", 1.0, ["F4"])]

    def test_title_beats_abstract_and_topics_recorded(self):
        s1, t1 = rank_mod.score_item(
            item(title="Truly Subquadratic 3SUM", published="2026-10-05"),
            self.topics, 3.0, today=date(2026, 10, 7))
        s2, t2 = rank_mod.score_item(
            item(title="Unrelated", abstract="mentions 3SUM once",
                 published="2026-10-05"),
            self.topics, 3.0, today=date(2026, 10, 7))
        self.assertGreater(s1, s2)
        self.assertEqual(t1, ["fine-grained"])
        self.assertEqual(t2, ["fine-grained"])

    def test_short_tokens_need_word_boundaries(self):
        s, t = rank_mod.score_item(item(title="F40 valves", abstract=""),
                                   self.topics, 3.0)
        self.assertEqual(s, 0.0)
        self.assertEqual(t, [])
        s, t = rank_mod.score_item(item(title="Matrix F4 engine", abstract=""),
                                   self.topics, 3.0)
        self.assertGreater(s, 0.0)

    def test_recency_and_tiers(self):
        fresh = item(title="3SUM", published="2026-10-06")
        old = item(title="3SUM", published="2020-01-01")
        sf, _ = rank_mod.score_item(fresh, self.topics, 3.0, today=date(2026, 10, 7))
        so, _ = rank_mod.score_item(old, self.topics, 3.0, today=date(2026, 10, 7))
        self.assertGreater(sf, so)
        self.assertEqual(rank_mod.tier_of(8.0, 8.0, 3.0), "candidate")
        self.assertEqual(rank_mod.tier_of(7.9, 8.0, 3.0), "watch")
        self.assertEqual(rank_mod.tier_of(2.9, 8.0, 3.0), "noise")


class ReportTests(unittest.TestCase):
    def test_digest_sections(self):
        scored = [
            (item(title="Big One", url="http://x", published="2026-10-06",
                  authors=["A"], abstract="abstract here"), 12.0, "candidate", ["t"]),
            (item(title="Small One", url="http://y"), 4.0, "watch", []),
        ]
        text = report_mod.render(scored, 7, "2026-10-07", 2)
        self.assertIn("## Breakthrough candidates", text)
        self.assertIn("## Watch list", text)
        self.assertIn("[Big One](http://x)", text)
        self.assertIn("topics: t", text)


class ConfigTests(unittest.TestCase):
    def test_defaults_and_toml(self):
        cfg = config_mod.load(None)
        self.assertEqual(cfg.topics, [])
        self.assertEqual(cfg.title_mult, 3.0)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.toml"
            config_mod.write_default(p)
            cfg = config_mod.load(p)
            names = [t.name for t in cfg.topics]
            self.assertIn("fine-grained", names)
            self.assertIn("cs.CR", cfg.arxiv_categories)
            self.assertGreater(len(cfg.eprint_queries), 0)


if __name__ == "__main__":
    unittest.main()
