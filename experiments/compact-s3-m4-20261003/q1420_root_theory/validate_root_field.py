#!/usr/bin/env python3
"""Cross-check the native S3 root oracle against the archived Python oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from run_probe import field  # noqa: E402
from s3_root_oracle import s3_roots  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--degree", type=int, choices=(53, 83), required=True)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    n = args.degree
    assert args.samples >= 0
    onb = field.Onb(n)
    fixture_name = ("n53_q1410_witness_locked.json" if n == 53 else
                    "n83_q1408_planted_locked.json")
    fixture = json.loads((PARENT / "runs" / fixture_name).read_text())
    leaves = fixture["fixture"]["raw_leaf_x"]
    pairs = [(leaves[0], leaves[1]), (leaves[2], leaves[3])]
    rng = random.Random(142000 + n)
    pairs.extend((rng.randrange(1, 1 << n), rng.randrange(1, 1 << n))
                 for _ in range(args.samples))
    binary = HERE / "root_field_cli"
    assert binary.is_file()
    counts = {"zero": 0, "one": 0, "two": 0}
    for a, b in pairs:
        expected = [onb.toCoords(root) for root in s3_roots(
            onb, onb.fromCoords(a), onb.fromCoords(b))]
        result = subprocess.run([str(binary), str(HERE / f"n{n}_field.txt"),
                                 f"{a:x}", f"{b:x}"], capture_output=True,
                                text=True, check=True)
        observed = [int(line, 16) for line in result.stdout.splitlines()]
        assert observed == expected, (n, a, b, expected, observed)
        counts[{0: "zero", 1: "one", 2: "two"}[len(observed)]] += 1
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        "kind": "q1420_native_root_crosscheck",
        "status": "PASS", "degree_n": n,
        "curve_id": fixture["curve_id"],
        "fixture_pairs": 2, "sampled_pairs": args.samples,
        "sample_seed": 142000 + n,
        "root_count_histogram": counts,
        "field_bridge_export_sha256": sha(HERE / f"n{n}_field.txt"),
        "field_bridge_manifest_sha256": sha(
            PARENT / "field_bridges" / f"n{n}_onb_poly.json"),
        "fixture_receipt_sha256": sha(PARENT / "runs" / fixture_name),
        "native_binary_sha256": sha(binary),
        "source_sha256": sha(Path(__file__)),
        "is_natural_relation_yield_measurement": False,
        "complete_solve_work_log2": None,
    }
    output = HERE / f"n{n}_root_validation.json"
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.emit:
        assert not output.exists()
        output.write_text(content)
    if args.check:
        assert output.read_text() == content
    print(json.dumps({"status": "PASS", "degree": n,
                      "fixture_pairs": 2, "sampled_pairs": args.samples,
                      "root_count_histogram": counts}))


if __name__ == "__main__":
    main()
