#!/usr/bin/env sage -python
"""Freeze 32 target-independent signed W16 first-pair choices."""

import hashlib
import importlib.util
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n131_w16_fivepair_sat_gate_20261010"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load("joint_prefix_old_run", OLD / "fivepair_run.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    prior = json.loads((OLD / "fivepair_input.json").read_text())
    columns, field, curve, _, _ = old.experiment.run.source()
    _, _, _, basis_w, basis_u = old.lift.original.source()
    available = sorted(columns)
    rng = random.Random(20261010)
    point_cache = {}

    def raw_atom(mask):
        if mask not in point_cache:
            point_cache[mask] = old.lift.original.atom(
                field, curve, basis_w, basis_u, mask)
        return point_cache[mask]

    def row(a, b, sign_a, sign_b):
        leaves = [raw_atom(a), raw_atom(b)]
        if sign_a:
            leaves[0] = curve.neg(leaves[0])
        if sign_b:
            leaves[1] = curve.neg(leaves[1])
        raw = curve.add(*leaves)
        projected = curve.mul(4, raw)
        if raw is None or projected is None:
            return None
        return {"masks": [a, b], "signs": [sign_a, sign_b],
                "columns": [columns[a], columns[b]],
                "raw_leaves": [list(point) for point in leaves],
                "raw_sum": list(raw), "projected_sum": list(projected)}

    a, b = prior["first_pair_masks"]
    initial = None
    for sign_a in (0, 1):
        for sign_b in (0, 1):
            candidate = row(a, b, sign_a, sign_b)
            if candidate["raw_sum"] == prior["first_pair_raw"]:
                initial = candidate
    assert initial is not None
    assert initial["projected_sum"] == prior["first_pair_projected"]
    prefixes = [initial]
    seen = {tuple(initial["projected_sum"])}
    while len(prefixes) < 32:
        a, b = rng.sample(available, 2)
        if columns[a] == columns[b]:
            continue
        sign_a, sign_b = rng.randrange(2), rng.randrange(2)
        candidate = row(a, b, sign_a, sign_b)
        if candidate is None or tuple(candidate["projected_sum"]) in seen:
            continue
        prefixes.append(candidate)
        seen.add(tuple(candidate["projected_sum"]))
    target = tuple(prior["original_target_q"])
    for prefix in prefixes:
        residual = curve.add(target, curve.neg(tuple(prefix["projected_sum"])))
        assert residual is not None
        prefix["residual_q"] = list(residual)
        preimages = old.experiment.run.prior.prior.old.target_preimages(curve, residual)
        assert len(preimages) == 4 and all(point[0] for point in preimages)
        prefix["preimages"] = [list(point) for point in preimages]
        prefix["target_reciprocals"] = [field.inv(point[0]) for point in preimages]
    assert prefixes[0]["residual_q"] == prior["residual_target_q"]
    record = {"status": "FROZEN_32_SIGNED_FIRST_PAIR_CHOICES",
              "curve_id": prior["curve_id"], "target_law":
              "constructed twelve-point control; signed first-pair list fixed independently of future targets",
              "target_q": list(target), "prefix_count": len(prefixes),
              "sampling_seed": 20261010, "prefixes": prefixes,
              "source_sha256": {"preparation": sha(HERE / "prepare.py"),
                                "original_input": sha(OLD / "fivepair_input.json"),
                                "original_runner": sha(OLD / "fivepair_run.py"),
                                "support": sha(ROOT / "n131_w16_w18_sixpair_width_gate_20261010" /
                                               "support_w16.tsv")}}
    with (HERE / "prefixes.json").open("x") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": record["status"], "count": len(prefixes),
                      "positive_index": 0}))


if __name__ == "__main__":
    main()
