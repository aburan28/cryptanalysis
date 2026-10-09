#!/usr/bin/env sage -python
"""Check frozen N41 join slot wiring and paired-sum composition before search."""

import hashlib
import json
import random
from pathlib import Path

import run_join as join

HERE = Path(__file__).resolve().parent
BASE = join.BASE


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    source = json.loads((BASE / "protocol.json").read_text())
    table = json.loads((BASE / "table.json").read_text())
    if (protocol["status"] != "FROZEN" or
            protocol["source_sha256"]["run_join"] != sha(HERE / "run_join.py")):
        raise ValueError("join source changed after freeze")
    onb = join.field.Onb(41)
    curve = join.curves.Curve(onb)
    options = join.build_options(onb, curve, table["valid_codes"],
                                 table["basis_coordinate_masks"])
    first = join.first_root_options(onb, curve, options, table)
    pairs = join.pair_lists(curve, options)
    root_phi = onb.fromCoords(table["selected_first_link_root"])
    root_x = onb.add(onb.inv(root_phi), onb.one())
    if len(first) != 2:
        raise ValueError("first-link signed root count changed")
    for root, (i, j) in first:
        if (root[0] != root_x or
                curve.add(options[0][i][2], options[1][j][2]) != root):
            raise ValueError("first signed root does not match two leaves")
    rng = random.Random(20261009141000)
    for side in ("left", "right"):
        for _ in range(100):
            ordinal = rng.randrange(60 ** 5)
            start = 2 if side == "left" else 7
            digits = join.decode(ordinal)
            direct = join.point_sum(curve,
                                    [options[start + k][digit][2]
                                     for k, digit in enumerate(digits)])
            indexed = join.five_sum(curve, options, pairs, ordinal, side)
            if direct != indexed:
                raise ValueError("indexed five-sum differs from direct addition")
    target = tuple(onb.fromCoords(v) for v in source["target_coordinates"])
    endpoint = curve.mul(target, pow(4, -1, source["subgroup_order"]))
    if endpoint != tuple(onb.fromCoords(v)
                         for v in source["endpoint_coordinates"]):
        raise ValueError("target endpoint differs from frozen source")
    receipt = {"kind": "n41_phi_five_plus_five_join_preflight",
               "status": "PASS_EXACT_SLOTS_ROOT_AND_SUMS",
               "slot_count": 12, "signed_options_per_slot": 60,
               "checked_five_sums_per_side": 100,
               "pair_list_sizes": {str(key): len(rows)
                                   for key, rows in pairs.items()},
               "first_root_signed_branches": len(first),
               "source_sha256": {"protocol": sha(HERE / "protocol.json"),
                                 "run_join": sha(HERE / "run_join.py"),
                                 "preflight": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"]}))


if __name__ == "__main__":
    main()
