#!/usr/bin/env python3
"""Replay selected XOR-seed pair counts by direct mask enumeration."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w15_coupled_sixpair_20261010" / "support_w15.tsv"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((HERE / "seed_result.json").read_text())
    data = (HERE / "seed_class_counts.bin").read_bytes()
    bits = (HERE / "class_bits.bin").read_bytes()
    assert len(data) == (1 << 15)*8
    columns = {}
    groups = defaultdict(list)
    for row in SUPPORT.read_text().splitlines():
        mask, column = map(int, row.split())
        columns[mask] = column
        groups[column].append(mask)
    seeds = set(range(1, 65))
    seeds.update(row[0] for key in ("top_class0_seeds", "bottom_class0_seeds")
                 for row in result["distribution"][key])
    for seed in sorted(seeds):
        same = different = 0
        for mask, column in columns.items():
            other = mask ^ seed
            if other not in columns or columns[other] == column:
                continue
            if bits[mask] == bits[other]:
                same += 1
            else:
                different += 1
        expected0 = int.from_bytes(data[8*seed:8*seed+4], "little")
        expected1 = int.from_bytes(data[8*seed+4:8*seed+8], "little")
        assert (2*same, 2*different) == (expected0, expected1)
    total0 = sum(int.from_bytes(data[8*s:8*s+4], "little")
                 for s in range(1, 1 << 15))
    total1 = sum(int.from_bytes(data[8*s+4:8*s+8], "little")
                 for s in range(1, 1 << 15))
    assert (total0, total1) == (result["totals"]["0"], result["totals"]["1"])
    receipt = {"status": "PASS_INDEPENDENT_W15_SEED_CLASS_COUNTS",
               "seeds_brute_forced": len(seeds),
               "ordered_mask_pairs_checked_upper": len(seeds)*len(columns),
               "totals": {"0": total0, "1": total1},
               "sha256": {"script": sha(Path(__file__)),
                          "seed_result": sha(HERE / "seed_result.json"),
                          "counts": sha(HERE / "seed_class_counts.bin"),
                          "class_bits": sha(HERE / "class_bits.bin"),
                          "support": sha(SUPPORT)}}
    with (HERE / "seed_audit.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "seeds_brute_forced": receipt["seeds_brute_forced"]}))


if __name__ == "__main__":
    main()
