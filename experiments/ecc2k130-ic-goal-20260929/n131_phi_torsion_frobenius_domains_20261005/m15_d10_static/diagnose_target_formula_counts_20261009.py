#!/usr/bin/env python3
"""Compare the frozen official-Q formula with the first d10 precompute query."""

import hashlib
import json
import random
from pathlib import Path

import run_d10_m15_single_target as runner

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(runner.MANIFEST.read_text())
    protocol = json.loads(runner.PROTOCOL.read_text())
    workload = json.loads(runner.WORKLOAD.read_text())
    curve_data = json.loads(runner.CURVE_RECORD.read_text())
    assert json.loads((HERE / "single_target_preflights/d10_m15_20261009T175525Z.json").read_text())["status"] == "READY"
    context, official_q, base, _operations = runner.build_context(
        curve_data, workload, manifest)
    onb, curve, order, _eigenvalue, generator, basis_masks, _representatives, \
        _lookup, _key_to_column, valid_codes, _official_q, fiber_coordinates = context
    first_scalar = random.Random(protocol["run_control"]["precomputation_seed"]).randrange(1, order)
    first_target = curve.mul(generator, first_scalar)
    assert first_target is not None and first_target != official_q
    cases = {}
    for label, target in (("official_q", official_q),
                          ("precomputation_001", first_target)):
        formula, _primary, roots, _fiber, _phi_masks = \
            runner.pipeline.target_relation_formula(
                onb, curve, order, target, basis_masks, valid_codes,
                official_q, fiber_coordinates)
        cases[label] = {"stats": formula.stats(), "roots": len(roots),
                        "target_coordinates": [onb.toCoords(value) for value in target]}
    expected = json.loads((HERE / "d10_m15_formula_and_planted_control_v1.json").read_text())["formula_counts"]
    result = {
        "status": "PASS",
        "expected_official_q": expected,
        "cases": cases,
        "first_precompute_scalar_sha256": hashlib.sha256(str(first_scalar).encode()).hexdigest(),
        "base_point_set_sha256": base["enumerated_point_set_sha256"],
        "source_sha256": {"diagnostic": sha(Path(__file__)),
                          "runner": sha(runner.__file__),
                          "pipeline": sha(HERE / "sparse_seed_d10_m15_pipeline.py"),
                          "formula_receipt": sha(HERE / "d10_m15_formula_and_planted_control_v1.json")},
    }
    path = HERE / "diagnose_target_formula_counts_20261009.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "official": cases["official_q"]["stats"],
                      "precompute": cases["precomputation_001"]["stats"]}, sort_keys=True))


if __name__ == "__main__":
    main()
