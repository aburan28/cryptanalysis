#!/usr/bin/env python3
"""Audit the certified Voronoi corner decision and frozen scalar panel."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PARENT = ROOT / "experiments/prime-j0-exact-reciprocal-20261010/screen.py"
FROZEN = ROOT / "experiments/prime-j0-radix943-word-20261009/inputs.json"
PRIOR = ROOT / "experiments/prime-j0-exact-reciprocal-20261010/fresh-inputs.json"
FRESH = HERE / "fresh-inputs.json"
RESULT = HERE / "screen-result.json"
SEED = 20261010217
COUNT = 4096
B = 1 << 64
T = 1 << 512

spec = importlib.util.spec_from_file_location("reciprocal_parent", PARENT)
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_digest(values):
    return hashlib.sha256(b"".join(k.to_bytes(32, "big") for k in values)).hexdigest()


def selected_corners(k, qw, qv):
    entries = []
    for corner, (dw, dv) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
        a = k - (qw + dw) * parent.W0 - (qv + dv) * parent.V0
        b = -(qw + dw) * parent.W1 - (qv + dv) * parent.V1
        norm = a * a + 3 * a * b + 3 * b * b
        entries.append((norm, max(abs(a), abs(b)), a, b, corner))
    return entries


def certificate(hw, hv):
    a10 = B - 2 * hw + hv
    a01 = B + hw - 2 * hv
    a11 = B - hw - hv
    bounds = ((0, 0), (a10 - 4, a10 + 2),
              (a01 - 4, a01 + 2), (a11 - 4, a11))
    winners = [i for i, (_, upper) in enumerate(bounds)
               if all(upper < lower for j, (lower, _) in enumerate(bounds) if j != i)]
    assert len(winners) <= 1
    return (winners[0] if winners else None), bounds


def generate():
    if FRESH.exists():
        raise SystemExit("fresh input file already exists")
    frozen = json.loads(FROZEN.read_text())
    prior = json.loads(PRIOR.read_text())
    seen = {int(value, 16) % parent.N for value in frozen["scalars_hex"]}
    seen.update(int(value, 16) for value in prior["scalars_hex"])
    rng = random.Random(SEED)
    values = []
    while len(values) < COUNT:
        value = rng.randrange(parent.N)
        if value not in seen:
            values.append(value)
            seen.add(value)
    result = {"schema": 1, "seed": SEED, "count": COUNT,
              "frozen_input_sha256": sha(FROZEN), "prior_input_sha256": sha(PRIOR),
              "scalar_sha256": scalar_digest(values),
              "scalars_hex": [f"{value:064x}" for value in values]}
    FRESH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"count": COUNT, "scalar_sha256": result["scalar_sha256"]}))


def audit():
    if RESULT.exists():
        raise SystemExit("screen result already exists")
    parent.check_source_constants()
    frozen = json.loads(FROZEN.read_text())
    prior = json.loads(PRIOR.read_text())
    fresh = json.loads(FRESH.read_text())
    frozen_values = [int(value, 16) for value in frozen["scalars_hex"]]
    prior_values = [int(value, 16) for value in prior["scalars_hex"]]
    fresh_values = [int(value, 16) for value in fresh["scalars_hex"]]
    assert len(frozen_values) == 519 and len(prior_values) == COUNT
    assert len(fresh_values) == COUNT and fresh["seed"] == SEED
    assert fresh["frozen_input_sha256"] == sha(FROZEN)
    assert fresh["prior_input_sha256"] == sha(PRIOR)
    assert scalar_digest(fresh_values) == fresh["scalar_sha256"]
    assert not set(fresh_values) & ({value % parent.N for value in frozen_values} |
                                   set(prior_values))
    rw = parent.reciprocal(parent.V1)
    rv = parent.reciprocal(-parent.W1)
    cases = (("boundary", [0, parent.N - 1, parent.N, (1 << 256) - 1]),
             ("frozen", frozen_values), ("prior", prior_values),
             ("holdout", fresh_values))
    panel = {}
    point_replays = 0
    tau_point = parent.multiply(parent.LAMBDA_TAU, (parent.GX, parent.GY))
    for name, values in cases:
        fallback = 0
        certified_counts = [0, 0, 0, 0]
        checked = 0
        for raw in values:
            k = raw % parent.N
            xw, xv = k * rw, k * rv
            qw, qv = xw >> 512, xv >> 512
            hw, hv = (xw & (T - 1)) >> 448, (xv & (T - 1)) >> 448
            assert qw == k * parent.V1 // parent.N
            assert qv == k * (-parent.W1) // parent.N
            rem_w = k * parent.V1 - qw * parent.N
            rem_v = k * (-parent.W1) - qv * parent.N
            assert 0 <= rem_w < parent.N and 0 <= rem_v < parent.N
            assert hw * parent.N <= B * rem_w < (hw + 2) * parent.N
            assert hv * parent.N <= B * rem_v < (hv + 2) * parent.N
            corners = selected_corners(k, qw, qv)
            true_deltas = (0, parent.N - 2 * rem_w + rem_v,
                           parent.N + rem_w - 2 * rem_v,
                           parent.N - rem_w - rem_v)
            for index, delta in enumerate(true_deltas):
                assert corners[index][0] - corners[0][0] == delta
            selected = min(corners)
            winner, bounds = certificate(hw, hv)
            for index, (lower, upper) in enumerate(bounds):
                assert lower * parent.N <= B * true_deltas[index] <= upper * parent.N
            if winner is None:
                fallback += 1
            else:
                assert winner == selected[4]
                certified_counts[winner] += 1
            assert (selected[2] + selected[3] * parent.LAMBDA_TAU - k) % parent.N == 0
            if name == "holdout" and point_replays < 128:
                found = parent.add(parent.multiply(selected[2], (parent.GX, parent.GY)),
                                   parent.multiply(selected[3], tau_point))
                expected = parent.multiply(k, (parent.GX, parent.GY))
                assert found == expected
                point_replays += 1
            checked += 1
        panel[name] = {"cases": checked, "certified_by_corner": certified_counts,
                       "fallbacks": fallback}
    result = {"schema": 1, "status": "passed", "panels": panel,
              "independent_holdout_point_replays": point_replays,
              "fresh_scalar_sha256": fresh["scalar_sha256"],
              "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in
                                (Path(__file__), HERE / "PROTOCOL.md", FROZEN, PRIOR,
                                 FRESH, PARENT)}}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "panels": panel,
                      "independent_holdout_point_replays": point_replays}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "audit"))
    args = parser.parse_args()
    {"generate": generate, "audit": audit}[args.command]()
