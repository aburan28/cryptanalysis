#!/usr/bin/env python3
"""Replay the known n53 ordinary relation in the rational-filtered formula."""

import base64
import gzip
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path

from chain_s3_multitarget import decode_choice
from chain_s3_rational import build_rational_multitarget
from run_probe import HERE, curves, field, lift, parse_model, sha


def main():
    witness_path = HERE / "runs/n53_ordinary_raw_pair_witness.json"
    stage_path = HERE / "runs/n53_ordinary_rational.json"
    coset_path = HERE / "runs/n53_ordinary_raw_preimages.json"
    support_path = HERE / "bases/n53_weight3_nonrational_supports.json.gz"
    output = HERE / "runs/n53_ordinary_rational_locked_verify.json"
    assert not output.exists()
    witness = json.loads(witness_path.read_text())
    stage = json.loads(stage_path.read_text())
    coset = json.loads(coset_path.read_text())
    with gzip.open(support_path, "rt") as stream:
        support = json.load(stream)
    packed = base64.b64decode(support["nonrational_supports_base64"])
    assert hashlib.sha256(packed).hexdigest() == support[
        "nonrational_supports_sha256"]
    invalid = [int.from_bytes(packed[index:index + 7], "little")
               for index in range(0, len(packed), 7)]
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    xs = coset["raw_target_x_coordinates"]
    leaf_xs = [onb.toCoords(int(point[0]))
               for point in witness["raw_leaf_points"]]
    mid_xs = witness["intermediate_x_coordinates"]
    raw = tuple(int(v) for v in witness["raw_target"])
    public = tuple(int(v) for v in witness["public_target"])
    choice = xs.index(onb.toCoords(raw[0]))
    assert choice == 201
    formula, leaves, mids, _, selector = build_rational_multitarget(
        53, 3, xs, invalid)
    with tempfile.TemporaryDirectory() as name:
        path = Path(name) / "unlocked.xcnf"
        formula.write(path)
        assert sha(path) == stage["xcnf_sha256"]
        for row, value in zip(leaves, leaf_xs):
            formula.clauses.extend(([bit if value >> i & 1 else -bit]
                                    for i, bit in enumerate(row)))
        for row, value in zip(mids, mid_xs):
            formula.clauses.extend(([bit if value >> i & 1 else -bit]
                                    for i, bit in enumerate(row)))
        formula.clauses.extend(([bit if choice >> i & 1 else -bit]
                                for i, bit in enumerate(selector)))
        locked_path = Path(name) / "locked.xcnf"
        formula.write(locked_path)
        locked_sha = sha(locked_path)
        began = time.perf_counter()
        result = subprocess.run(["cryptominisat5", "--verb", "0",
                                 "--threads", "1", str(locked_path)],
                                capture_output=True, text=True, timeout=30)
        wall_seconds = time.perf_counter() - began
    assert result.returncode == 10, result.stdout[-1000:]
    values = parse_model(result.stdout)
    assert values is not None and decode_choice(selector, values) == choice
    leaf_coords, relation, status = lift(onb, curve, leaves, values,
                                         raw, public, 428)
    assert leaf_coords == leaf_xs and relation is not None
    assert status == "verified_four_point_relation"
    receipt = {
        "kind": "n53_rational_filtered_locked_raw_relation_control",
        "proposal_id": "Q1308",
        "candidate_id": None,
        "workload_id": stage["workload_id"],
        "curve_id": stage["curve_id"],
        "isogeny": "none",
        "status": "verified_locked_sat_relation",
        "choice_index": choice,
        "leaf_x_coordinates": leaf_coords,
        "relation": relation,
        "solver_wall_seconds": wall_seconds,
        "locked_xcnf_sha256": locked_sha,
        "unlocked_xcnf_sha256": stage["xcnf_sha256"],
        "stage_receipt_sha256": sha(stage_path),
        "witness_receipt_sha256": sha(witness_path),
        "coset_receipt_sha256": sha(coset_path),
        "support_archive_sha256": sha(support_path),
        "source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "choice_index": choice,
                      "solver_wall_seconds": wall_seconds}))


if __name__ == "__main__":
    main()
