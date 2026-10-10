#!/usr/bin/env python3
"""Freeze positive pair outputs and uniform field controls before timing."""
import hashlib
import json
import random
from pathlib import Path

import oracle

HERE = Path(__file__).resolve().parent
SUPPORT = HERE.parent / "n131_w14_ten_source_gate_20261009"
OFFICIAL = HERE.parent / "n131_w2_m15_official_single_target_4g_20261003"
SEED = 202610102210


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def sources():
    return {"freeze": Path(__file__), "runner": HERE / "run.py",
            "oracle": HERE / "oracle.py",
            "field": oracle.REPLAY / "independent_replay.py",
            "support_protocol": SUPPORT / "support_protocol.json",
            "support_audit": SUPPORT / "sage_support_audit.json",
            "support_masks": SUPPORT / "support_w14.tsv",
            "official_params": OFFICIAL / "official_fixed_parameters.json",
            "official_bridge": OFFICIAL / "bridge_audit.json"}


def main():
    support = json.loads((SUPPORT / "support_protocol.json").read_text())
    audit = json.loads((SUPPORT / "sage_support_audit.json").read_text())
    bridge = json.loads((OFFICIAL / "bridge_audit.json").read_text())
    assert support["status"] == "FROZEN_BEFORE_ENUMERATION"
    assert audit["status"] == "PASS_FULL_MASKS_ORBITS_AND_TEN_WINDOW_BASE"
    assert bridge["status"] == "PASS"
    assert support["curve_id"] == "EC1N131Ckb1heb5f1998f20b"
    columns = oracle.load_support(SUPPORT / "support_w14.tsv")
    candidate = oracle.PairOracle(columns)
    assert oracle.solve(oracle.echelon(candidate.basis_u)[0], 1) is None
    rng = random.Random(SEED)
    groups = {}
    for mask, canonical in columns.items():
        groups.setdefault(canonical, []).append(mask)
    keys = sorted(groups)
    positives = []
    attempts = 0
    while len(positives) < 32:
        attempts += 1
        selected = rng.sample(keys, 2)
        a, b = [rng.choice(groups[key]) for key in selected]
        signs = [rng.randrange(2) for _ in range(2)]
        left = candidate.point_options(a)[signs[0]]
        right = candidate.point_options(b)[signs[1]]
        total = candidate.curve.add(left, right)
        z = candidate.phi_of(total)
        if z is None:
            continue
        positives.append({"kind": "positive", "masks": [a, b],
                          "folded_columns": selected, "signs": signs,
                          "raw_leaves": [list(left), list(right)],
                          "raw_sum": list(total), "z": z})
    controls = []
    for _ in range(32):
        z = rng.getrandbits(131)
        if z in (0, 1):
            raise AssertionError("uniform control accidentally exceptional")
        controls.append({"kind": "uniform_field", "z": z})
    controls += [{"kind": "exceptional", "z": 0},
                 {"kind": "exceptional", "z": 1}]
    inputs = {"status": "FROZEN_INPUTS", "seed": SEED,
              "positive_draw_attempts": attempts,
              "positives": positives, "controls": controls}
    save(HERE / "inputs.json", inputs)
    record = {"status": "FROZEN_BEFORE_PAIR_QUERIES",
              "candidate_id": None, "curve_id": support["curve_id"],
              "factor_base_policy": "five rotations each used twice, W14 source",
              "rotations": [0, 0, 26, 26, 52, 52, 78, 78, 104, 104],
              "actual_factor_base_points_B": 82200,
              "effective_folded_columns_K": audit["folded_columns_K"],
              "rational_source_masks": len(columns),
              "positive_count": len(positives),
              "uniform_field_control_count": 32,
              "exceptional_count": 2,
              "full_scan_comparator_indices": {"positive": 0,
                                               "uniform_field": 0},
              "wall_cap_seconds": 120,
              "rss_cap_bytes": 4*1024**3,
              "inputs_sha256": sha(HERE / "inputs.json"),
              "source_sha256": {name: sha(path)
                                for name, path in sources().items()}}
    save(HERE / "protocol.json", record)
    print(json.dumps({"status": record["status"],
                      "positives": len(positives),
                      "uniform_controls": 32,
                      "B": record["actual_factor_base_points_B"]}))


if __name__ == "__main__":
    main()
