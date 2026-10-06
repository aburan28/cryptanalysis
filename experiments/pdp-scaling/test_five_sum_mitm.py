"""End-to-end witness and resource-gate checks for the native point solver."""

import json
import lzma
from pathlib import Path
import subprocess
import tempfile
import unittest

from gf2n import Curve, GF2n, Point

HERE = Path(__file__).resolve().parent


class ExactFiveSumTests(unittest.TestCase):
    def test_witness_and_memory_gate(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            exe = d / "solver"
            subprocess.run(["g++", "-std=c++17", "-O3", "-Wall", "-Wextra", "-Werror",
                            str(HERE / "five_sum_mitm.cpp"), "-o", str(exe)], check=True)
            archive = HERE / "explicit-base-frontier-20260928/run-1/n13-l5.jsonl.xz"
            lines = [json.loads(s) for s in lzma.decompress(archive.read_bytes()).splitlines()]
            reps = sorted({(int(p["projected_x"], 16), int(p["projected_y"], 16))
                           for p in lines if "projected_x" in p})
            curve = Curve(GF2n(13), 1)
            points = [Point(*p) for p in reps[:6]]
            points += [curve.neg(p) for p in points]
            base = d / "base.tsv"
            base.write_text("".join(f"{p.x:x} {p.y:x}\n" for p in points))
            target = curve.sum(points[:5])
            targets = d / "targets.tsv"
            targets.write_text(f"{target.x:x} {target.y:x}\n")
            modulus = str(curve.F.mod)
            def call(summands, limit=50000, path=base):
                return subprocess.run([str(exe), "13", modulus, str(path), str(targets),
                                       str(limit), "5", "1", str(summands)], capture_output=True, text=True)
            result = call(5)
            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(result.stdout)
            self.assertEqual(row["status"], "found")
            self.assertEqual(curve.sum(points[i] for i in row["witness"]), target)
            small = call(5, 1)
            self.assertEqual(json.loads(small.stdout)["status"], "budget")
            direct = call(3)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            if json.loads(direct.stdout)["status"] == "found":
                self.assertEqual(curve.sum(points[i] for i in json.loads(direct.stdout)["witness"]), target)
            invalid = d / "bad.tsv"
            invalid.write_text("0 0\n")
            self.assertNotEqual(call(5, path=invalid).returncode, 0)
            huge = d / "too-large.tsv"
            # 2,000 points imply more than the explicit 1.5m pair entry cap.
            huge.write_text((base.read_text().splitlines()[0] + "\n") * 2000)
            self.assertIn("pair table exceeds", call(5, path=huge).stderr)


if __name__ == "__main__":
    unittest.main()
