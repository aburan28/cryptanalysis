#!/usr/bin/env python3
"""Independent replay of Q20261010190000's sample and arithmetic."""

import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(PARENT), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    receipt = json.loads((HERE / "run.json").read_text())
    frozen = json.loads((HERE / "freeze.json").read_text())
    sample = receipt["sample"]
    assert frozen["curve_id"] == receipt["curve_id"] == (
        "EC1N131Ckb1h6816f880945e")
    assert sample["size"] == frozen["sample_size"] == 250_000
    assert sample["seed"] == frozen["seed"]
    onb = field.Onb(131)
    curve = curves.Curve(onb)
    rng = random.Random(sample["seed"])
    visited = set()
    stream = hashlib.sha256()
    positives = 0
    for index in range(sample["size"]):
        while True:
            positions = rng.sample(range(131), 7)
            mask = 0
            for position in positions:
                mask |= 1 << position
            if mask not in visited:
                visited.add(mask)
                break
        x = onb.fromCoords(mask)
        # Separate trace identity and 64 direct lift checks.
        answer = onb.trace(x ^ onb.inv(x)) == 0
        if index < 64:
            assert (curve.pointFromX(x) is not None) == answer
            assert sample["curve_lift_replay"][index] == {
                "mask": mask, "rational": answer}
        positives += answer
        stream.update(mask.to_bytes(17, "little"))
        stream.update(bytes((answer,)))
    assert positives == sample["rational"]
    assert stream.hexdigest() == sample["support_classification_sha256"]
    exact = [json.loads((PARENT / f"runs/n131_q1413_projected_x_w{w}.json").read_text())
             for w in (5, 6)]
    assert [(d["actual_usable_points_B_before_folding"],
             d["signed_frobenius_columns_K"]) for d in exact] == [
                 (309633434, 1181807), (6559634788, 25036774)]
    rows = receipt["rows"]
    assert [row["weight_bound"] for row in rows] == [5, 6, 7, 8]
    assert rows[0]["actual_B_or_conditional_B"] == 309633434
    assert rows[1]["actual_B_or_conditional_B"] == 6559634788
    p = positives / sample["size"]
    b7 = 6559634788 + 2*math.comb(131, 7)*p
    k7 = 25036774 + math.comb(131, 7)*p/131
    assert math.isclose(rows[2]["actual_B_or_conditional_B"], b7)
    assert math.isclose(rows[2]["folded_K_or_conditional_K"], k7)
    assert rows[2]["B_interval_conditional"][0] < b7 < (
        rows[2]["B_interval_conditional"][1])
    r = frozen["subgroup_order_r"]
    for row in rows:
        b, k = row["actual_B_or_conditional_B"], row[
            "folded_K_or_conditional_K"]
        mean = math.comb(math.ceil(b)+3, 4)/(r-1)
        checks = (
            ("log2_mean_representations_upper", math.log2(mean)),
            ("all_models_uniform_query_lower_bound_log2",
             math.log2(max(1, math.ceil(k/mean)))),
            ("one_novel_row_per_query_lower_bound_log2", math.log2(math.ceil(k))),
            ("matrix_4K2_touch_model_log2", math.log2(4*k*k)),
            ("matrix_8K2_touch_model_log2", math.log2(8*k*k)))
        for name, value in checks:
            assert math.isclose(row[name], value, abs_tol=1e-10)
    result = {"status": "PASS", "proposal_id": receipt["proposal_id"],
              "run_sha256": sha(HERE / "run.json"),
              "auditor_source_sha256": sha(__file__),
              "sample_replayed": sample["size"],
              "curve_lift_controls": 64,
              "sample_classification_sha256": stream.hexdigest(),
              "rows_recomputed": 4}
    path = HERE / "audit.json"
    assert not path.exists()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
