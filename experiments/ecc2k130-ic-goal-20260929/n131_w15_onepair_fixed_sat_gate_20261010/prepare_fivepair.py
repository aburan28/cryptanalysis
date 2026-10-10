#!/usr/bin/env sage -python
"""Subtract the known signed first pair from the constructed W15 target."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
W15 = HERE.parent / "n131_w15_coupled_sixpair_20261010"
ORIGINAL = HERE.parent / "n131_w14_coupled_sixpair_sat_20261010"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    experiment = load("prepare_fivepair_experiment", W15 / "experiment.py")
    _, field, curve, _, control = experiment.run.source()
    witness = json.loads((W15 / "control_group_lift.json").read_text())["solutions"][0]
    leaves = [tuple(point) for point in witness["raw_leaves"]]
    assert control["target_q"] == witness["projected_sum"]
    pair_sums = [curve.add(leaves[2*i], leaves[2*i+1]) for i in range(6)]
    assert all(point is not None and point[0] != 0 for point in pair_sums)
    def reciprocal(point):
        assert point is not None and point[0] != 0
        return field.inv(point[0])
    first_pair = pair_sums[0]
    raw_residual = curve.add(tuple(witness["raw_sum"]), curve.neg(first_pair))
    remainder = None
    for point in pair_sums[1:]:
        remainder = curve.add(remainder, point)
    assert raw_residual == remainder
    residual_q = curve.mul(4, raw_residual)
    assert curve.add(residual_q, curve.mul(4, first_pair)) == tuple(control["target_q"])
    lifts = experiment.run.prior.prior.old.target_preimages(curve, residual_q)
    target_index = next(i for i, point in enumerate(lifts) if point == raw_residual)
    remaining = pair_sums[1:]
    upper0 = curve.add(remaining[0], remaining[1])
    upper1 = curve.add(remaining[2], remaining[3])
    upper2 = curve.add(upper0, upper1)
    middle = [reciprocal(point) for point in remaining + [upper0, upper1, upper2]]
    assert len(middle) == 8
    assert curve.add(upper2, remaining[4]) == raw_residual
    record = {
        "status": "PASS_EXACT_CONSTRUCTED_W15_FIVE_PAIR_RESIDUAL",
        "candidate_id": None,
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "original_target_q": control["target_q"],
        "first_pair_raw": list(first_pair),
        "first_pair_projected": list(curve.mul(4, first_pair)),
        "first_pair_masks": witness["masks"][:2],
        "first_pair_columns": witness["folded_columns"][:2],
        "residual_target_q": list(residual_q),
        "residual_raw": list(raw_residual),
        "residual_target_preimage_index": target_index,
        "remaining_masks": witness["masks"][2:],
        "remaining_columns": witness["folded_columns"][2:],
        "remaining_middle_reciprocals": middle,
        "source_sha256": {"script": sha(__file__),
                          "w15_experiment": sha(W15 / "experiment.py"),
                          "w15_group_lift": sha(W15 / "control_group_lift.json"),
                          "original_control": sha(ORIGINAL / "control.json"),
                          "runtime": sha(HERE / "sage_runtime_info.json")},
    }
    with (HERE / "fivepair_input.json").open("x") as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": record["status"],
                      "residual_target_q": record["residual_target_q"]}))


if __name__ == "__main__":
    main()
