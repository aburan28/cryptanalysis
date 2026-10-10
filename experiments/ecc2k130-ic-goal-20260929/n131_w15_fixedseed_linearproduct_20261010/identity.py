#!/usr/bin/env sage -python
"""Exhaustively check the fixed-seed linear product on usable W15 pairs."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"
SEED = 12004


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("fixedseed_identity_base", BASE / "experiment.py")
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    columns, field, _, basis_w, _ = base.run.source()
    seed = 0
    for bit, basis in enumerate(basis_w):
        if SEED >> bit & 1:
            seed ^= basis
    images = [field.mul(basis, basis) ^ field.mul(seed, basis)
              for basis in basis_w]
    checked = 0
    for a, column in columns.items():
        b = a ^ SEED
        if b not in columns or column == columns[b]:
            continue
        w_a = 0
        w_b = 0
        linear = 0
        for bit, basis in enumerate(basis_w):
            if a >> bit & 1:
                w_a ^= basis
                linear ^= images[bit]
            if b >> bit & 1:
                w_b ^= basis
        assert w_a ^ w_b == seed
        assert field.mul(w_a, w_b) == linear
        checked += 1
    count = json.loads((HERE / "support_count.json").read_text())
    assert checked == 2*count["fixed_seed_unordered_distinct_column_mask_pairs"]
    receipt = {"status": "PASS_EXHAUSTIVE_FIXEDSEED_LINEAR_PRODUCT",
               "seed": SEED,
               "ordered_usable_mask_pairs_checked": checked,
               "field_identity": "w_a*w_b = w_a^2 + s*w_a for w_b=w_a+s",
               "sha256": {"script": sha(Path(__file__)),
                          "source": sha(BASE / "experiment.py"),
                          "support_count": sha(HERE / "support_count.json")}}
    with (HERE / "identity.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "ordered_usable_mask_pairs_checked": checked}))


if __name__ == "__main__":
    main()
