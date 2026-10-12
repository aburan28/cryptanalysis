#!/usr/bin/env python3
"""Check shared-guard root clauses against exhaustive S3 truth at degree 11."""

import argparse
import json
import subprocess
import sys
import tempfile
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def run(binary, cnf, mapping, policy, encoding):
    command = [str(binary), str(cnf), str(mapping), str(STAGE),
               str(ROOT / "ecc2k130/codegen"), policy, encoding,
               "2", "100", "10"]
    result = subprocess.run(command, text=True, capture_output=True,
                            timeout=20, check=False)
    assert result.returncode in (10, 20), (command, result.returncode,
                                            result.stdout, result.stderr)
    return json.loads(result.stdout.splitlines()[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    onb = field.Onb(11)
    examples = {}
    for a_coord in range(1, 32):
        if a_coord.bit_count() != 2:
            continue
        for b_coord in range(1, 32):
            if b_coord.bit_count() != 2:
                continue
            a, b = onb.fromCoords(a_coord), onb.fromCoords(b_coord)
            roots = tuple(onb.toCoords(c) for c in s3_roots(onb, a, b))
            if len(roots) not in examples:
                exhaustive = tuple(c for c in range(1 << 11)
                                   if evaluate_s3(onb, a, b, onb.fromCoords(c)) == 0)
                assert roots == exhaustive
                examples[len(roots)] = (a_coord, b_coord, roots)
            if len(examples) == 3:
                break
        if len(examples) == 3:
            break
    assert set(examples) == {0, 1, 2}
    second_a, second_b = 1, 1
    second_roots = tuple(onb.toCoords(c) for c in s3_roots(
        onb, onb.fromCoords(second_a), onb.fromCoords(second_b)))
    assert len(second_roots) == 1
    rows = [[1 + 11 * row + i for i in range(11)] for row in range(6)]
    checked = []
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        mapping = directory / "s3.map"
        mapping.write_text("11\n" + "\n".join(" ".join(map(str, row))
                                      for row in rows) + "\n")
        for root_count, (a, b, roots) in sorted(examples.items()):
            wrong = next(c for c in range(1 << 11) if c not in roots)
            for c in (*roots, wrong):
                cnf = directory / "s3.cnf"
                with cnf.open("w") as output:
                    output.write("p cnf 66 726\n")
                    for row, value in zip(rows,
                                          (a, b, second_a, second_b,
                                           c, second_roots[0])):
                        for i, var in enumerate(row):
                            output.write(f"{var if value & (1 << i) else -var} 0\n")
                    for row in rows[:4]:
                        for triple in combinations(row, 3):
                            output.write(" ".join(str(-var) for var in triple) + " 0\n")
                off = run(args.binary, cnf, mapping, "off", "shared")
                assert off["status"] == 10
                expected = 10 if c in roots else 20
                stats = {}
                for encoding in ("legacy", "pivot", "shared", "satpivot", "satlegacy"):
                    stats[encoding] = run(args.binary, cnf, mapping, "none", encoding)
                    assert stats[encoding]["status"] == expected
                    assert stats[encoding]["root_queries"] >= 1
                checked.append({"root_count": root_count, "pair": [a, b],
                                "middle": c, "expected": expected,
                                "saturated_leaves_seen": stats["satpivot"][
                                    "saturated_leaves_seen"],
                                "satpivot_guard_literals": stats["satpivot"][
                                    "guard_literals_total"]})
    print(json.dumps({"status": "PASS", "degree": 11,
                      "exhaustive_middle_coordinates_per_pair": 1 << 11,
                      "checked_instances": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
