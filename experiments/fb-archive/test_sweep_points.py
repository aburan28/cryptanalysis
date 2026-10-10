"""Sweep point shards: exact point sets, reproducible to the digests committed in git."""

from __future__ import annotations

import csv
import hashlib
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sweep_points  # noqa: E402
import sweeps  # noqa: E402
from purepy import PyField  # noqa: E402


def committed(name: str) -> dict:
    with open(sweep_points.index_path(name), newline="") as fh:
        return {r["label"]: r for r in csv.DictReader(fh)}


def counter(doc: dict) -> sweeps.Counter:
    return sweeps.Counter(doc["field"]["degree"], sum(1 << e for e in doc["field"]["modulus_exponents"]))


class ShardTest(unittest.TestCase):
    def test_every_sweep_has_a_digest_per_curve(self):
        for name in sweeps.BUILDERS:
            doc = sweeps.load(name)
            rows = committed(name)
            self.assertEqual(list(rows), [c["label"] for c in doc["curves"]], name)
            self.assertEqual({r["curve_id"] for r in rows.values()}, {c["curve_id"] for c in doc["curves"]})

    def test_sampled_shards_reproduce_their_digests(self):
        for name in sweeps.BUILDERS:
            doc = sweeps.load(name)
            ctr = counter(doc)
            rows = committed(name)
            curves = random.Random(name).sample(doc["curves"], 2 if name == "ecc2k130-isogeny-class" else 4)
            for curve in curves:
                content, _ = sweep_points.shard(doc, curve, ctr)
                self.assertEqual(hashlib.sha256(content).hexdigest(), rows[curve["label"]]["content_sha256"],
                                 (name, curve["label"]))

    def test_records_are_rational_abscissae(self):
        doc = sweeps.load("volcano-ic")
        K = PyField(19, sweeps.VIC_MOD)
        curve = doc["curves"][3]
        header, fams = sweep_points.decode(sweep_points.shard(doc, curve, counter(doc))[0])
        self.assertEqual(header["label"], curve["label"])
        basis = doc["families"]["prefix10"]["basis"]
        recs = fams["prefix10"]
        self.assertEqual(recs[0], (0, 0))
        kept = {c for c, _ in recs}
        for c in range(1, 1 << 10):
            x = 0
            for i in range(10):
                if c >> i & 1:
                    x ^= basis[i]
            rational = K.trace(x ^ K.mul(curve["b"], K.inv(K.sqr(x)))) == 0
            self.assertEqual(c in kept, rational, c)
        self.assertTrue(all(x == c for c, x in recs))  # the z^i basis makes x = c

    def test_counts_match_the_experiment(self):
        doc = sweeps.load("volcano-ic")
        rec = sweeps.vic_recorded()
        ctr = counter(doc)
        for curve in doc["curves"][:20]:
            _, counts = sweep_points.shard(doc, curve, ctr)
            self.assertEqual(counts["prefix10"][10], rec[(curve["label"], "prefix10", 10)])

    def test_trailing_bytes_are_rejected(self):
        doc = sweeps.load("volcano-ic")
        content, _ = sweep_points.shard(doc, doc["curves"][0], counter(doc))
        with self.assertRaises(ValueError):
            sweep_points.decode(content + b"\0")


if __name__ == "__main__":
    unittest.main()
