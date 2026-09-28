"""Exercise compiled base points against the independent Python curve model."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from explicit_base_frontier import CONTROLS, SOURCE, necessary_B, verify_case


class ExplicitBaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.tmp.name) / "enumerator"
        subprocess.run(["g++", "-O3", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(SOURCE), "-o", str(cls.binary)], check=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exact_small_controls(self):
        for n, l, expected_B in ((13, 5, 26), (83, 6, 52)):
            with self.subTest(n=n):
                ref = json.loads(CONTROLS[n].read_text())
                raw = Path(self.tmp.name) / f"n{n}.jsonl"
                with raw.open("w") as out:
                    subprocess.run([str(self.binary), str(n), str(l), str(ref["base"]["modulus"])],
                                   stdout=out, check=True, timeout=30)
                result = verify_case(raw, ref, {"n": n, "l": l, "seed": 117, "sample_size": 32})
                self.assertEqual(result["signed_projected_B"], expected_B)
                self.assertTrue(result["independent_control_set_match"])
                self.assertGreater(result["independent_sample_checks"], 10)

    def test_forged_projection_and_incomplete_receipt_rejected(self):
        ref = json.loads(CONTROLS[13].read_text())
        raw = Path(self.tmp.name) / "forged.jsonl"
        with raw.open("w") as out:
            subprocess.run([str(self.binary), "13", "5", str(ref["base"]["modulus"])],
                           stdout=out, check=True, timeout=30)
        lines = raw.read_text().splitlines()
        first = json.loads(lines[0]); first["projected_y"] = "0"
        lines[0] = json.dumps(first)
        raw.write_text("\n".join(lines) + "\n")
        with self.assertRaises(ValueError):
            verify_case(raw, ref, {"n": 13, "l": 5, "seed": 117, "sample_size": 32})
        raw.write_text("\n".join(lines[:-1]) + "\n")
        with self.assertRaises(ValueError):
            verify_case(raw, ref, {"n": 13, "l": 5, "seed": 117, "sample_size": 32})

    def test_integer_necessary_bound(self):
        r = 2417851639230796216685689
        for m in (3, 4, 5):
            B = necessary_B(r, m)
            self.assertLess((B-1)**m * 100, r-1)
            self.assertGreaterEqual(B**m * 100, r-1)


if __name__ == "__main__":
    unittest.main()
