"""Check the compact S3 circuit against exact curve arithmetic."""

import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from chain_s3 import build, evaluate_s3, multiplication_table
from run_probe import lift, parse_model
from ecc2k130.codegen import curves, field


class ChainS3Tests(unittest.TestCase):
    def test_multiplication_table(self):
        for n in (5, 53, 83):
            onb = field.Onb(n)
            table = multiplication_table(onb)
            rng = random.Random(n)
            for _ in range(12):
                a = rng.getrandbits(n)
                b = rng.getrandbits(n)
                got = 0
                for i in range(n):
                    if a >> i & 1:
                        for j in range(n):
                            if b >> j & 1:
                                got ^= table[i][j]
                self.assertEqual(got, onb.toCoords(onb.mul(
                    onb.fromCoords(a), onb.fromCoords(b))))

    @unittest.skipUnless(shutil.which("cryptominisat5"), "CryptoMiniSat absent")
    def test_planted_four_points_satisfy_circuit(self):
        onb = field.Onb(5)
        curve = curves.Curve(onb)
        points = [curve.pointFromX(onb.fromCoords(x))
                  for x in range(1, 1 << 5) if x.bit_count() <= 2]
        points = [point for point in points if point is not None]
        rng = random.Random(19)
        while True:
            chosen = [rng.choice(points) for _ in range(4)]
            first = curve.add(chosen[0], chosen[1])
            second = curve.add(first, chosen[2])
            target = curve.add(second, chosen[3])
            if first and second and target and target[0]:
                break
        for values in ((chosen[0][0], chosen[1][0], first[0]),
                       (first[0], chosen[2][0], second[0]),
                       (second[0], chosen[3][0], target[0])):
            self.assertEqual(evaluate_s3(onb, *values), 0)
        formula, leaves, mids = build(5, 2, onb.toCoords(target[0]))
        for variables, point in zip(leaves, chosen):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        for variables, point in zip(mids, (first, second)):
            value = onb.toCoords(point[0])
            formula.clauses.extend(([var if value >> i & 1 else -var]
                                    for i, var in enumerate(variables)))
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "planted.xcnf"
            formula.write(path)
            result = subprocess.run(["cryptominisat5", "--verb", "0",
                                     "--threads", "1", str(path)],
                                    capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 10, result.stdout[-500:])
        coords, relation, status = lift(onb, curve, leaves,
                                        parse_model(result.stdout), target,
                                        curve.mul(target, 4), 4)
        self.assertEqual(status, "verified_four_point_relation")
        self.assertEqual(coords, [onb.toCoords(p[0]) for p in chosen])
        self.assertIsNotNone(relation)


if __name__ == "__main__":
    unittest.main()
