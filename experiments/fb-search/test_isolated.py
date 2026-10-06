"""Tests for the one-target IC-versus-rho isolated-benchmark harness (isolated/)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "isolated"))

import make_ic_isolated_manifest as mk  # noqa: E402
import one_target  # noqa: E402


def load_runner():
    spec = importlib.util.spec_from_file_location("isolated_bench", ROOT / "scripts" / "isolated_bench.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fields(stdout: str) -> dict:
    return dict(w.split("=", 1) for w in stdout.strip().splitlines()[-1].split() if "=" in w)


class HarnessTest(unittest.TestCase):
    def test_fixture_law_is_frozen(self):
        C = one_target.ToyCurve(19)
        a = [one_target.fixture_scalar("k", C, i) for i in range(5)]
        self.assertEqual(a, [one_target.fixture_scalar("k", C, i) for i in range(5)])
        self.assertTrue(all(1 <= s < C.r for s in a))
        self.assertEqual(len(set(a)), 5)

    def test_manifest_passes_the_runners_schema(self):
        m = mk.build(Path(sys.executable), ROOT, Path("/sys/fs/cgroup/benchmark-isolated"), "2-3", 3, "0",
                     {19: 2, 23: 1}, 600)
        cpus, nodes, cgroup = load_runner().require_manifest(m)
        self.assertEqual((cpus, nodes), ({2, 3}, {0}))
        self.assertEqual(len(m["cases"]), 3)
        self.assertEqual([c["reference"][3] for c in m["cases"]], ["rho"] * 3)
        self.assertEqual([c["candidate"][3] for c in m["cases"]], ["ic"] * 3)

    def test_both_variants_verify_the_same_target(self):
        common = [sys.executable, str(HERE / "isolated" / "one_target.py"), "--n", "13", "--family", "prefix",
                  "--l", "4", "--seed", "1", "--mode", "ht", "--rerandomize", "walk", "--panel-key", "test",
                  "--index", "3"]
        out = {}
        for v in ("ic", "rho"):
            p = subprocess.run(common[:2] + ["--variant", v] + common[2:], capture_output=True, text=True, timeout=600)
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])
            out[v] = fields(p.stdout)
            self.assertEqual(out[v]["verified"], "1")
            self.assertGreater(float(out[v]["online_ms"]), 0)
        for k in mk.build(Path(sys.executable), ROOT, Path("/sys/fs/cgroup/x"), "0", 0, "0", {19: 1}, 1)["pair_fields"]:
            self.assertEqual(out["ic"][k], out["rho"][k], k)
        self.assertTrue(out["ic"]["candidate_id"].startswith("IC1N13Ckb1fb"))


if __name__ == "__main__":
    unittest.main()
