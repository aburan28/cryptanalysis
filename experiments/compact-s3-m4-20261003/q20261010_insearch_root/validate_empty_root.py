#!/usr/bin/env python3
"""Check an in-search no-root conflict against exhaustive GF(2^11) replay."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[1]
sys.path.insert(0, str(STAGE))
from chain_s3 import evaluate_s3, field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    onb = field.Onb(11)
    pair = None
    for a_coord in range(1, 16):
        for b_coord in range(1, 16):
            a, b = onb.fromCoords(a_coord), onb.fromCoords(b_coord)
            if not s3_roots(onb, a, b):
                pair = a_coord, b_coord
                break
        if pair is not None:
            break
    assert pair is not None
    a, b = (onb.fromCoords(value) for value in pair)
    assert all(evaluate_s3(onb, a, b, onb.fromCoords(c)) != 0
               for c in range(1 << 11))
    rows = [[1 + 11 * row + i for i in range(11)] for row in range(6)]
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        mapping = directory / "rootless.map"
        mapping.write_text("11\n" + "\n".join(" ".join(map(str, row))
                                      for row in rows) + "\n")
        cnf = directory / "rootless.cnf"
        with cnf.open("w") as stream:
            stream.write("p cnf 66 22\n")
            for row, value in zip(rows[:2], pair):
                for i, var in enumerate(row):
                    stream.write(f"{var if value & (1 << i) else -var} 0\n")
        results = {}
        for mode in ("off", "none"):
            command = [str(args.binary), str(cnf), str(mapping), str(STAGE),
                       str(ROOT / "ecc2k130/codegen"), mode, "100", "10"]
            run = subprocess.run(command, text=True, capture_output=True,
                                 timeout=20, check=False)
            assert run.returncode in (10, 20), run.stderr
            results[mode] = json.loads(run.stdout.splitlines()[0])
        assert results["off"]["status"] == 10
        assert results["none"]["status"] == 20
        assert results["none"]["root_queries"] == 1
        assert results["none"]["empty_root_pairs"] == 1
        print(json.dumps({"status": "PASS", "degree": 11,
                          "rootless_pair_coordinates": pair,
                          "exhaustive_third_coordinate_count": 1 << 11,
                          "off_solver_status": 10,
                          "propagator_solver_status": 20}, sort_keys=True))


if __name__ == "__main__":
    main()
