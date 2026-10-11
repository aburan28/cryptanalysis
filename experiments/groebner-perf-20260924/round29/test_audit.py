"""Corrupt real measurement records and full build receipts deliberately."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import audit

HERE = Path(__file__).resolve().parent
BUNDLE = None


class MeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(gzip.decompress((HERE / "results/measure.json.gz").read_bytes()))
        cls.control = json.loads((HERE / "results/correctness.json").read_text())

    def rejects(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        with self.assertRaises(ValueError):
            audit.measurement(data)

    def test_real_control(self):
        audit.measurement(self.data)
        audit.correctness(self.control)

    def test_excluded_correctness_timing(self):
        data = copy.deepcopy(self.control)
        data["timing_eligible"] = True
        with self.assertRaises(ValueError):
            audit.correctness(data)

    def test_missing_pair(self):
        self.rejects(lambda d: d["cells"][0]["samples"].pop())

    def test_matrix_substitution(self):
        self.rejects(lambda d: d["cells"][0].update(name="different-matrix"))

    def test_wrong_rank(self):
        self.rejects(lambda d: d["cells"][0]["samples"][0].update(rank=0))

    def test_warmup_included_as_measurement(self):
        self.rejects(lambda d: d["cells"][0]["samples"][0].update(warmup=False))

    def test_duplicate_arm(self):
        self.rejects(lambda d: d["cells"][0]["samples"][1].update(order=[0, 1, 1, 3]))

    def test_overloaded_group(self):
        self.rejects(lambda d: d["cells"][0]["samples"][1].update(load1=d["logical_cpus"]+1))

    def test_bad_time(self):
        for value in (-1, 0, float("nan"), float("inf"), True):
            self.rejects(lambda d: d["cells"][0]["samples"][1].update(active16_wall_ms=value))

    def test_omitted_wall_cost(self):
        self.rejects(lambda d: d["cells"][0]["samples"][1].update(active16_wall_ms=0.0001))

    def test_missing_panel_work(self):
        self.rejects(lambda d: d["cells"][0]["samples"][1].update(active32_local=True, active32_panels16=0, active32_panels32=0))


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        if BUNDLE is None:
            self.skipTest("a fresh full native bundle is required")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bundle"
        shutil.copytree(BUNDLE, self.path)

    def test_current_sources(self):
        self.assertEqual(audit.audit(self.path)["status"], "PASS")

    def test_tampered_binary(self):
        with (self.path / "active-rref").open("ab") as out:
            out.write(b"altered")
        with self.assertRaisesRegex(ValueError, "binary hash"):
            audit.audit(self.path)

    def test_self_consistent_but_untrusted_source(self):
        source = self.path / "sources/round29/active_panel.metal"
        source.write_text(source.read_text() + "\n// altered\n")
        receipt_path = self.path / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["sources"]["round29/active_panel.metal"] = audit.sha(source)
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "trusted current source"):
            audit.audit(self.path)

    def test_forged_run_entrypoint(self):
        path = self.path / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["runs"]["correctness"]["command"][0] = "/some/other-program"
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "run entrypoint"):
            audit.audit(self.path)

    def test_changed_library(self):
        path = self.path / "receipt.json"
        receipt = json.loads(path.read_text())
        receipt["runs"]["correctness"]["loaded_m4ri_sha256"] = "0"*64
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "loaded library identity"):
            audit.audit(self.path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    args, remaining = parser.parse_known_args()
    BUNDLE = args.bundle
    unittest.main(argv=[__file__, *remaining])
