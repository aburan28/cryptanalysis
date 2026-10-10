#!/usr/bin/env sage -python
"""Choose a signed W15 prefix without consulting the public target."""

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_w15_coupled_sixpair_20261010"
PRIOR = HERE.parent / "n131_w15_onepair_fixed_sat_gate_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    assert runtime["status"] == "verified"
    prior = json.loads((PRIOR / "fivepair_input.json").read_text())
    original = json.loads((BASE / "query_protocol.json").read_text())
    lift = load("unrestricted_prefix_lift", BASE / "w15_lift.py")
    columns, field, curve, basis_w, basis_u = lift.source()
    control_columns = set(prior["remaining_columns"])
    selected = []
    for mask in sorted(columns):
        column = columns[mask]
        if column in control_columns or column in [item[1] for item in selected]:
            continue
        selected.append((mask, column))
        if len(selected) == 2:
            break
    assert len(selected) == 2
    masks = [item[0] for item in selected]
    folded = [item[1] for item in selected]
    points = [lift.atom(field, curve, basis_w, basis_u, mask) for mask in masks]
    pair_raw = curve.add(*points)
    assert pair_raw is not None and pair_raw[0] != 0
    prefix_q = curve.mul(4, pair_raw)
    assert prefix_q is not None and len(set(folded + prior["remaining_columns"])) == 12
    public_q = tuple(original["target_q"])
    residual_q = curve.add(public_q, curve.neg(prefix_q))
    assert residual_q is not None
    assert curve.add(residual_q, prefix_q) == public_q
    constructed_residual_q = tuple(prior["residual_target_q"])
    constructed_full_q = curve.add(constructed_residual_q, prefix_q)
    assert constructed_full_q is not None
    record = {
        "status": "PASS_TARGET_INDEPENDENT_PREFIX_AND_RESIDUALS",
        "candidate_id": None,
        "curve_id": original["curve_id"],
        "selection_rule": "first two increasing W15 rational masks with distinct folded columns outside the archived constructed residual control",
        "prefix_masks": masks,
        "prefix_columns": folded,
        "prefix_signs": [0, 0],
        "prefix_raw_leaves": [list(point) for point in points],
        "prefix_raw_sum": list(pair_raw),
        "prefix_projected_sum": list(prefix_q),
        "public_target_q": list(public_q),
        "public_residual_target_q": list(residual_q),
        "constructed_full_target_q": list(constructed_full_q),
        "constructed_residual_target_q": prior["residual_target_q"],
        "constructed_residual_raw": prior["residual_raw"],
        "constructed_residual_preimage_index": prior["residual_target_preimage_index"],
        "constructed_remaining_masks": prior["remaining_masks"],
        "constructed_remaining_middle_reciprocals": prior["remaining_middle_reciprocals"],
        "source_sha256": {"script": sha(Path(__file__)),
                          "checked_runtime": sha(HERE / "sage_runtime_info.json"),
                          "w15_lift": sha(BASE / "w15_lift.py"),
                          "w15_support": sha(BASE / "support_w15.tsv"),
                          "prior_control": sha(PRIOR / "fivepair_input.json"),
                          "public_protocol": sha(BASE / "query_protocol.json")},
    }
    with (HERE / "input.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": record["status"], "prefix_masks": masks,
                      "prefix_columns": folded,
                      "public_residual_target_q": list(residual_q)}))


if __name__ == "__main__":
    main()
