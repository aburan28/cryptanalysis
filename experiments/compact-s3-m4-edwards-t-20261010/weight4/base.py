#!/usr/bin/env python3
"""Exact orbit-representative enumeration of the N53 t-coordinate base."""

import argparse
import hashlib
import itertools
import json
import math
import platform
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
Q1419 = ROOT / "experiments/compact-s3-m4-20261003/q1419_partial_pin"
sys.path[:0] = [str(PARENT), str(ROOT / "experiments/compact-s3-m4-20261003"),
                str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3 import square_destinations  # noqa: E402
from t_link import t_of_x, x_roots_of_t  # noqa: E402

PROPOSAL = "Q20261010174100"
FREEZE = HERE / "freeze.json"
PARENT_RUN = PARENT / "run.json"
PARENT_BASE = PARENT / "bases/n53_t_weight3_columns.bin"
Q1419_PROTOCOL = Q1419 / "protocol.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def pack(keys):
    return b"".join(value.to_bytes(7, "little") for value in sorted(keys))


def freeze():
    q1419 = load(Q1419_PROTOCOL)["profiles"]["53"]
    parent = load(PARENT_RUN)["n53_t_base"]
    assert parent["curve_id"] == q1419["curve_id"]
    assert digest(PARENT_BASE) == parent["enumerated_set_sha256"]
    save(FREEZE, {"schema": "q20261010174100-freeze-v1",
        "proposal_id": PROPOSAL, "candidate_id": None, "run_id": None,
        "isogeny": "none", "field_degree_n": 53,
        "curve_id": q1419["curve_id"], "cofactor": q1419["cofactor"],
        "subgroup_order_r": q1419["subgroup_order_r"],
        "ordinary_workload_id": q1419["workload_id"],
        "parent_w3_B": parent["actual_usable_points_B"],
        "parent_w3_K": parent["folded_columns_K"],
        "parent_w3_digest": digest(PARENT_BASE),
        "parent_run_sha256": digest(PARENT_RUN),
        "q1419_protocol_sha256": digest(Q1419_PROTOCOL),
        "t_link_source_sha256": digest(PARENT / "t_link.py"),
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "base.py", "audit.py")},
        "weight_bounds": [3, 4]})
    print(json.dumps({"freeze_sha256": digest(FREEZE)}))


def check_freeze():
    frozen = load(FREEZE)
    assert frozen["q1419_protocol_sha256"] == digest(Q1419_PROTOCOL)
    assert frozen["parent_run_sha256"] == digest(PARENT_RUN)
    assert frozen["parent_w3_digest"] == digest(PARENT_BASE)
    assert frozen["t_link_source_sha256"] == digest(PARENT / "t_link.py")
    for name, value in frozen["source_sha256"].items():
        assert value == digest(HERE / name)
    return frozen


def orbit(mask, destinations):
    values = []
    current = mask
    for _ in range(len(destinations)):
        values.append(current)
        next_mask = 0
        for index, target in enumerate(destinations):
            if current >> index & 1:
                next_mask |= 1 << target
        current = next_mask
    assert current == mask and len(set(values)) == len(destinations)
    return values


def canonical_x(f, x):
    values = []
    original = x
    for _ in range(f.m):
        values.append(f.toCoords(x))
        x = f.sqr(x)
    assert x == original and len(set(values)) == f.m
    return min(values)


def enumerate_base(frozen):
    n = frozen["field_degree_n"]
    f = field.Onb(n)
    e = curves.Curve(f)
    dest = square_destinations(f)
    seen = set()
    keys = set()
    outputs = []
    started = time.monotonic()
    for weight in range(1, 5):
        counts = {"nominal_masks": 0, "orbit_representatives": 0,
                  "quadratic_solvable_orbits": 0, "rational_orbits": 0,
                  "identity_projected_orbits": 0,
                  "duplicate_projected_columns": 0}
        for positions in itertools.combinations(range(n), weight):
            mask = sum(1 << i for i in positions)
            counts["nominal_masks"] += 1
            if mask in seen:
                continue
            cycle = orbit(mask, dest)
            seen.update(cycle)
            counts["orbit_representatives"] += 1
            t = f.fromCoords(mask)
            roots = x_roots_of_t(f, e, t)
            if not roots:
                continue
            assert len(roots) == 2 and all(t_of_x(f, x) == t for x in roots)
            counts["quadratic_solvable_orbits"] += 1
            point = e.pointFromX(roots[0])
            if point is None:
                continue
            counts["rational_orbits"] += 1
            projected = e.mul(point, frozen["cofactor"])
            if projected is None:
                counts["identity_projected_orbits"] += 1
                continue
            key = canonical_x(f, projected[0])
            if key in keys:
                counts["duplicate_projected_columns"] += 1
            else:
                keys.add(key)
        assert counts["nominal_masks"] == math.comb(n, weight)
        assert counts["orbit_representatives"] * n == counts[
            "nominal_masks"]
        if weight in (3, 4):
            data = pack(keys)
            path = HERE / "bases" / f"n53_t_weight{weight}_columns.bin"
            assert not path.exists()
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
            outputs.append({"weight_bound": weight,
                "nominal_t_masks": len(seen),
                "folded_columns_K": len(keys),
                "actual_usable_points_B": 2*n*len(keys),
                "enumerated_set_sha256": digest(path),
                "enumerated_set_bytes": len(data),
                "counts_by_weight": None,
                "elapsed_seconds_exploratory": time.monotonic()-started})
        if weight == 1:
            counts_by_weight = []
        counts_by_weight.append(counts)
    for row in outputs:
        row["counts_by_weight"] = counts_by_weight[:row["weight_bound"]]
    assert outputs[0]["actual_usable_points_B"] == frozen["parent_w3_B"]
    assert outputs[0]["folded_columns_K"] == frozen["parent_w3_K"]
    assert outputs[0]["enumerated_set_sha256"] == frozen["parent_w3_digest"]
    return outputs


def run():
    frozen = check_freeze()
    output = HERE / "run.json"
    assert not output.exists()
    rows = enumerate_base(frozen)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    save(output, {"schema": "q20261010174100-run-v1",
                  "proposal_id": PROPOSAL,
                  "candidate_id": None, "run_id": None,
                  "isogeny": "none", "curve_id": frozen["curve_id"],
                  "freeze_sha256": digest(FREEZE), "rows": rows,
                  "peak_process_rss_raw": usage.ru_maxrss,
                  "peak_process_rss_unit": "bytes" if platform.system() ==
                    "Darwin" else "kilobytes"})
    print(json.dumps({"status": "RECORDED", "w4_B": rows[1][
        "actual_usable_points_B"], "w4_K": rows[1]["folded_columns_K"],
        "run_sha256": digest(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check_freeze(); print("PASS: freeze")
    else:
        run()
