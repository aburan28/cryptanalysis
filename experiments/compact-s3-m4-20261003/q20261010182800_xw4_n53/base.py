#!/usr/bin/env python3
"""Exact N53 cofactor-projected x-weight-four orbit base."""

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
sys.path[:0] = [str(PARENT), str(ROOT / "ecc2k130/codegen")]
import field  # noqa: E402
import curves  # noqa: E402
from chain_s3 import square_destinations  # noqa: E402

PROPOSAL = "Q20261010182800"
PARENT_RUN = PARENT / "runs/n53_q1410_ordinary.json"
PARENT_PROTOCOL = PARENT / "q1410_balanced_s3_n53_protocol.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def orbit(mask, destinations):
    values = []
    current = mask
    for _ in range(len(destinations)):
        values.append(current)
        next_mask = 0
        for i, j in enumerate(destinations):
            if current >> i & 1:
                next_mask |= 1 << j
        current = next_mask
    assert current == mask and len(set(values)) == len(destinations)
    return values


def canonical_x(onb, x):
    values = []
    initial = x
    for _ in range(onb.m):
        values.append(onb.toCoords(x))
        x = onb.sqr(x)
    assert x == initial and len(set(values)) == onb.m
    return min(values)


def pack(keys):
    return b"".join(x.to_bytes(7, "little") for x in sorted(keys))


def freeze():
    parent, protocol = load(PARENT_RUN), load(PARENT_PROTOCOL)
    assert parent["proposal_id"] == protocol["proposal_id"] == "Q1410"
    assert parent["candidate_id"] is None and parent["isogeny"] == "none"
    assert parent["curve_id"] == protocol["curve_id"] == (
        "EC1N53Ckb1hf77aab617904")
    assert parent["workload_id"] == protocol["ordinary_workload_id"] == (
        "74f2979b3e68")
    assert parent["factor_base_actual_B"] == 24062
    assert parent["factor_base_folded_columns"] == 227
    save(HERE / "freeze.json", {
        "schema": "q20261010182800-freeze-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": parent["curve_id"], "workload_id": parent["workload_id"],
        "public_target": parent["public_target"],
        "cofactor": protocol["curve"]["cofactor"],
        "subgroup_order_r": int(protocol["curve"]["subgroup_order"]),
        "parent_w3_B": parent["factor_base_actual_B"],
        "parent_w3_K": parent["factor_base_folded_columns"],
        "parent_w3_digest": parent["factor_base_enumerated_set_sha256"],
        "parent_run_sha256": digest(PARENT_RUN),
        "parent_protocol_sha256": digest(PARENT_PROTOCOL),
        "field_source_sha256": digest(Path(field.__file__)),
        "curve_source_sha256": digest(Path(curves.__file__)),
        "source_sha256": {name: digest(HERE / name) for name in
                          ("PROTOCOL.md", "base.py", "audit.py")},
        "weight_bounds": [3, 4]})
    print(json.dumps({"freeze_sha256": digest(HERE / "freeze.json")}))


def check():
    frozen = load(HERE / "freeze.json")
    assert frozen["parent_run_sha256"] == digest(PARENT_RUN)
    assert frozen["parent_protocol_sha256"] == digest(PARENT_PROTOCOL)
    assert frozen["field_source_sha256"] == digest(Path(field.__file__))
    assert frozen["curve_source_sha256"] == digest(Path(curves.__file__))
    for name, value in frozen["source_sha256"].items():
        assert digest(HERE / name) == value
    return frozen


def enumerate_base(frozen):
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    assert curves.curveOrder(53) == frozen["cofactor"] * frozen[
        "subgroup_order_r"]
    destinations = square_destinations(onb)
    seen, keys, rows = set(), set(), []
    started = time.monotonic()
    for weight in range(1, 5):
        counts = {"weight": weight, "nominal_masks": 0,
                  "orbit_representatives": 0, "rational_orbits": 0,
                  "identity_projected_orbits": 0,
                  "duplicate_projected_columns": 0}
        for positions in itertools.combinations(range(53), weight):
            mask = sum(1 << i for i in positions)
            counts["nominal_masks"] += 1
            if mask in seen:
                continue
            cycle = orbit(mask, destinations)
            seen.update(cycle)
            counts["orbit_representatives"] += 1
            x = onb.fromCoords(mask)
            point = curve.pointFromX(x)
            if point is None:
                continue
            counts["rational_orbits"] += 1
            subgroup = curve.mul(point, frozen["cofactor"])
            if subgroup is None:
                counts["identity_projected_orbits"] += 1
                continue
            key = canonical_x(onb, subgroup[0])
            if key in keys:
                counts["duplicate_projected_columns"] += 1
            else:
                keys.add(key)
        assert counts["nominal_masks"] == math.comb(53, weight)
        assert counts["orbit_representatives"] * 53 == counts[
            "nominal_masks"]
        rows.append(counts)
        if weight in (3, 4):
            path = HERE / f"n53_x_weight{weight}_columns.bin"
            assert not path.exists()
            path.write_bytes(pack(keys))
            rows[-1]["cumulative_B"] = 106 * len(keys)
            rows[-1]["cumulative_K"] = len(keys)
            rows[-1]["enumerated_set_sha256"] = digest(path)
    assert rows[2]["cumulative_B"] == frozen["parent_w3_B"]
    assert rows[2]["cumulative_K"] == frozen["parent_w3_K"]
    assert rows[2]["enumerated_set_sha256"] == frozen["parent_w3_digest"]
    return rows, time.monotonic() - started


def run():
    frozen = check()
    rows, elapsed = enumerate_base(frozen)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    save(HERE / "run.json", {
        "schema": "q20261010182800-run-v1", "proposal_id": PROPOSAL,
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": frozen["curve_id"], "workload_id": frozen["workload_id"],
        "freeze_sha256": digest(HERE / "freeze.json"),
        "weight_bounds": frozen["weight_bounds"], "rows": rows,
        "actual_usable_points_B": rows[3]["cumulative_B"],
        "folded_columns_K": rows[3]["cumulative_K"],
        "enumerated_set_sha256": rows[3]["enumerated_set_sha256"],
        "elapsed_seconds_exploratory": elapsed,
        "peak_process_rss_raw": usage.ru_maxrss,
        "peak_process_rss_unit": "bytes" if platform.system() == "Darwin"
                                 else "kilobytes"})
    print(json.dumps({"B": rows[3]["cumulative_B"],
                      "K": rows[3]["cumulative_K"],
                      "elapsed_seconds_exploratory": elapsed}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "check", "run"))
    action = parser.parse_args().action
    if action == "freeze":
        freeze()
    elif action == "check":
        check(); print("PASS: freeze")
    else:
        run()
