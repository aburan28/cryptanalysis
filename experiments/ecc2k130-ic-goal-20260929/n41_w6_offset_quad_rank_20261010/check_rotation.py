"""Independently check every second-block output against Frobenius^10."""

import csv
import hashlib
import json
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULUS = (1 << 41) | (1 << 3) | 1


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, record):
    with path.open("x") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")


def square(value):
    expanded = 0
    for bit in range(41):
        if value >> bit & 1:
            expanded ^= 1 << (2 * bit)
    for bit in range(80, 40, -1):
        if expanded >> bit & 1:
            expanded ^= MODULUS << (bit - 41)
    return expanded


def main():
    names = ("quad_outputs.tsv", "quad_outputs_b.tsv", "rank_result.json",
             "rank_b.json", "check_rotation.py")
    write_new(HERE / "rotation_protocol_v2.json", {
        "status": "FROZEN_BEFORE_FROBENIUS_OUTPUT_AUDIT",
        "sha256": {name: digest(HERE / name) for name in names},
        "field_modulus": "t^41+t^3+1", "frobenius_power": 10,
    })
    original = csv.DictReader((HERE / "quad_outputs.tsv").open(newline=""), delimiter="\t")
    rotated = csv.DictReader((HERE / "quad_outputs_b.tsv").open(newline=""), delimiter="\t")
    checked = 0
    for a, b in zip_longest(original, rotated):
        assert a is not None and b is not None
        assert all(a[key] == b[key] for key in ("seed", "first_pair", "second_pair", "columns"))
        x, y = int(a["x"]), int(a["y"])
        for _ in range(10):
            x, y = square(x), square(y)
        assert (x, y) == (int(b["x"]), int(b["y"]))
        checked += 1
    assert checked == 51840
    first = json.loads((HERE / "rank_result.json").read_text())
    second = json.loads((HERE / "rank_b.json").read_text())
    assert [(row["seed"], row["distinct_x"], row["quadratic_rank"])
            for row in first["bins"]] == [(row["seed"], row["distinct_x"], row["quadratic_rank"])
                                        for row in second["bins"]]
    write_new(HERE / "rotation_audit.json", {
        "status": "PASS_ALL_N41_BLOCK_OUTPUT_FROBENIUS_AND_RANK",
        "checked_four_atom_witnesses": checked,
        "all_seed_rank_profiles_match": True,
        "protocol_sha256": digest(HERE / "rotation_protocol_v2.json"),
    })
    print("PASS_ALL_N41_BLOCK_OUTPUT_FROBENIUS_AND_RANK", checked)


if __name__ == "__main__":
    main()
