#!/usr/bin/env python3
"""Freeze one new public N53 target and the Q1473 base-log lookup."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from orbit_key import OrbitKey  # noqa: E402
from run_probe import curves, field  # noqa: E402

Q1468 = PARENT / "q1468_n53_pair_oracle"
Q1469 = PARENT / "q1469_n53_yield_panel"
Q1473 = PARENT / "q1473_n53_rank_collection"
TARGET_SEED = 14770053
LOGS = HERE / "base_logs.txt"
TARGET = HERE / "target.txt"
FIXTURE = HERE / "audit_fixture.json"
MANIFEST = HERE / "input_manifest.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def render() -> dict[Path, bytes]:
    design = json.loads((HERE / "design_protocol.json").read_text())
    assert design["proposal_id"] == "Q1477"
    parent = json.loads((PARENT / "protocol.json").read_text())
    curve_record = next(row["curve"] for row in parent["profiles"]
                        if row["curve"]["curve_id"] == design[
                            "exact_instance"]["curve_id"])
    q1473 = json.loads((Q1473 / "audit_result.json").read_text())
    assert q1473["status"] == "passed" and q1473["combined_rank"] == 26
    assert q1473["factor_base_actual_B"] == 2756
    assert q1473["factor_base_enumerated_set_sha256"] == design[
        "exact_instance"]["factor_base_enumerated_set_sha256"]
    r = curve_record["subgroup_order"]
    assert r == design["exact_instance"]["subgroup_order"]
    generator = tuple(curve_record["generator"])
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    assert curve.mul(generator, r) is None
    eigenvalue = curves.frobeniusEigenvalue(curve, generator, r)
    inverse_eigenvalue = pow(eigenvalue, -1, r)
    base_lines = (Q1468 / "inputs/base_points.txt").read_text().splitlines()
    assert base_lines[0] == "Q1468BASE1 53 2756 26"
    canonical_keys = {}
    point_logs = []
    q1473_logs = q1473["recovered_base_logs"]
    assert len(q1473_logs) == 26
    for index, line in enumerate(base_lines[1:]):
        column_text, x_text, y_text = line.split()
        column = int(column_text)
        point = (onb.fromCoords(int(x_text, 16)),
                 onb.fromCoords(int(y_text, 16)))
        key, exponent, sign = orbit.canonical(point)
        canonical_keys.setdefault(column, key)
        assert canonical_keys[column] == key
        value = sign * pow(inverse_eigenvalue, exponent, r) % r
        point_logs.append((index, column, value * q1473_logs[column] % r))
    assert len(point_logs) == 2756 and len(canonical_keys) == 26
    logs_bytes = ("Q1477LOGS1 53 2756 26 " + str(r) + "\n" +
                  "\n".join(f"{i} {column} {value}" for i, column, value
                            in point_logs) + "\n").encode()

    previous = set()
    for source in (Q1469 / "panel.json", Q1473 / "panel.json"):
        previous.update(tuple(row["public_target"])
                        for row in json.loads(source.read_text())["targets"])
    q1468 = json.loads((Q1468 / "protocol.json").read_text())
    previous.update(tuple(row["public_target"])
                    for row in q1468["workloads"].values())
    rng = random.Random(TARGET_SEED)
    skipped = 0
    while True:
        fixture_scalar = rng.randrange(1, r)
        public_target = curve.mul(generator, fixture_scalar)
        if public_target not in previous:
            break
        skipped += 1
    assert public_target is not None
    target_bytes = (f"Q1477TARGET1 53 {r}\n"
                    f"{int(onb.toCoords(generator[0])):x} "
                    f"{int(onb.toCoords(generator[1])):x}\n"
                    f"{int(onb.toCoords(public_target[0])):x} "
                    f"{int(onb.toCoords(public_target[1])):x}\n").encode()
    workload_record = {
        "curve_id": curve_record["curve_id"], "subgroup_order": r,
        "generator": list(generator), "public_target": list(public_target),
        "input_law": design["workload"]["target_law"],
        "target_seed": TARGET_SEED, "target_count": 1,
        "cache_state": design["workload"]["cache_state"],
    }
    workload_id = hashlib.sha256(canonical(workload_record)).hexdigest()[:12]
    fixture = {
        "kind": "q1477_target_fixture", "proposal_id": "Q1477",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "workload_id": workload_id, "workload_record": workload_record,
        "fixture_scalar": fixture_scalar, "excluded_prior_targets": len(previous),
        "skipped_prior_collisions": skipped,
        "target_file_sha256": hashlib.sha256(target_bytes).hexdigest(),
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
    }
    fixture_bytes = (json.dumps(fixture, sort_keys=True, indent=2) + "\n").encode()
    manifest = {
        "kind": "q1477_n53_one_target_inputs", "proposal_id": "Q1477",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": curve_record["curve_id"], "workload_id": workload_id,
        "factor_base_actual_B": 2756, "folded_columns_K": 26,
        "factor_base_enumerated_set_sha256": design[
            "exact_instance"]["factor_base_enumerated_set_sha256"],
        "source_sha256": sha(Path(__file__)),
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "q1473_audit_result_sha256": sha(Q1473 / "audit_result.json"),
        "q1468_base_points_sha256": sha(Q1468 / "inputs/base_points.txt"),
        "base_logs_sha256": hashlib.sha256(logs_bytes).hexdigest(),
        "target_file_sha256": hashlib.sha256(target_bytes).hexdigest(),
        "audit_fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    return {LOGS: logs_bytes, TARGET: target_bytes,
            FIXTURE: fixture_bytes, MANIFEST: manifest_bytes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    for path, content in render().items():
        if args.emit:
            assert not path.exists(), f"refuse overwrite: {path}"
            path.write_bytes(content)
        else:
            assert path.read_bytes() == content, path
    print(json.dumps({"status": "pass", "mode": "emit" if args.emit
                      else "check"}), flush=True)


if __name__ == "__main__":
    main()
