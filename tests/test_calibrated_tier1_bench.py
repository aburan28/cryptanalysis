"""Calibration and one-case promotion gates for the serial Tier 1 wrapper."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import calibrated_tier1_bench as runner  # noqa: E402


class CalibratedTier1Tests(unittest.TestCase):
    def test_calibrator_has_frozen_output(self):
        process = subprocess.run([str(ROOT / "scripts/tier1_calibrator.py")],
                                 capture_output=True, text=True, check=True)
        self.assertIn("verified=1", process.stdout)
        self.assertIn("calibration_id=sha256-32m-v1", process.stdout)
        self.assertIn("digest=b4ce437f949765dce16ec0d6c6b7c5a1d4ef209874ce9f04ee42984c06f14b40",
                      process.stdout)

    def test_spread_and_output_gate(self):
        spec = {"expected_fields": {"digest": "good"}, "max_spread_bps": 500}
        rows = [{"status": "valid", "fields": {"digest": "good"},
                 "online_ms": value} for value in (10.0, 10.2, 9.9, 10.1)]
        self.assertEqual(runner.calibration_issues(rows, spec)[0], [])
        rows[3]["online_ms"] = 11.0
        self.assertIn("A/A calibration spread exceeds frozen limit",
                      runner.calibration_issues(rows, spec)[0])
        rows[3]["online_ms"] = 10.1
        rows[1]["fields"]["digest"] = "wrong"
        self.assertIn("A/A calibration output mismatch",
                      runner.calibration_issues(rows, spec)[0])

    def test_tier1_manifest_requires_pinned_calibration(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            executable = root / "bench"
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
            receipt = root / "allocation.json"
            receipt.write_text(json.dumps({"provider": "runpod", "instance_id": "pod1"}))
            manifest = {
                "schema": 1, "workdir": str(root), "timeout_s": 30,
                "measurement_boundary": "internal scalar-dependent online_ms",
                "pair_fields": ["scalar"], "result_field": "point",
                "artifacts": [str(executable), str(receipt), str(Path(runner.__file__).resolve())],
                "isolation": {"tier": "tier1", "cpus": "4", "execution_cpu": 4,
                              "mem_nodes": "0", "cgroup": "/sys/fs/cgroup",
                              "allocation": {"provider": "runpod", "instance_id": "pod1",
                                             "receipt": str(receipt)}},
                "repetitions": 5,
                "cases": [{"id": "one", "reference": [str(executable)],
                           "candidate": [str(executable)],
                           "expected_fields": {"scalar": "1"},
                           "expected_result": "point1"}],
            }
            with self.assertRaisesRegex(ValueError, "A/A calibration"):
                runner.require_manifest(manifest)
            manifest["calibration"] = {
                "argv": [str(executable)], "expected_fields": {"digest": "abc"},
                "max_spread_bps": 500, "timeout_s": 10,
            }
            runner.require_manifest(manifest)
            manifest["calibration"]["max_spread_bps"] = 0
            with self.assertRaisesRegex(ValueError, "max_spread_bps"):
                runner.require_manifest(manifest)

    def test_aa_runs_bracket_pair_and_one_case_cannot_qualify(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            cal = root / "cal"
            cal.write_text("#!/bin/sh\nexit 0\n")
            cal.chmod(0o755)
            manifest = {"isolation": {"tier": "tier1"},
                        "calibration": {"argv": [str(cal)],
                                        "expected_fields": {"digest": "same"},
                                        "max_spread_bps": 500, "timeout_s": 1}}
            calls = []

            def fake_one_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                calls.append("cal" if argv[0] == str(cal) else argv[0])
                return {"serial": serial, "status": "valid", "issues": [],
                        "online_ms": 10.0 if argv[0] == str(cal) else 1.0,
                        "fields": {"verified": "1", "digest": "same"}}

            def fake_execute(value, output):
                output.mkdir()
                first = runner.base.one_run(["reference"], value, {4}, {0}, root, output, 1)
                second = runner.base.one_run(["candidate"], value, {4}, {0}, root, output, 2)
                self.assertEqual(first["status"], "valid")
                self.assertEqual(second["status"], "valid")
                return {"status": "completed", "speedup_qualified": True,
                        "paired_speedup": 2.0}

            with mock.patch.object(runner, "_one_run", side_effect=fake_one_run), \
                 mock.patch.object(runner, "_execute", side_effect=fake_execute):
                summary = runner.execute(manifest, root / "result")
            self.assertEqual(calls, ["cal", "cal", "reference", "candidate", "cal", "cal"])
            self.assertEqual(summary["calibration_pairs"], 1)
            self.assertEqual(summary["calibration_passed_pairs"], 1)
            self.assertFalse(summary["speedup_qualified"])
            self.assertIsNone(summary["paired_speedup"])
            self.assertEqual(summary["qualification_scope"], "one_case_stage")
            ledger = (root / "result/calibration_pairs.jsonl").read_text().splitlines()
            self.assertEqual(len(ledger), 1)
            self.assertEqual(json.loads(ledger[0])["status"], "valid")


if __name__ == "__main__":
    unittest.main()
