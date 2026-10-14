#!/usr/bin/env python3
"""Freeze and export exact N53 base, lifts, and common query indices for Q1454."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import platform
import random
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
PRIOR = ROOT / "experiments/koblitz-pair-claw-20260929"
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PRIOR))
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
from chain_s3 import square_destinations  # noqa: E402
from enumerate_weight_base import orbit  # noqa: E402
from probe_n53_relation import base_and_columns  # noqa: E402
from run_probe import curves, field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
FREEZE = HERE / "freeze.json"
STAGE = PARENT / "runs/n53_ordinary_frozen.json"
ARCHIVE = PARENT / "bases/n53_weight3_orbits.json.gz"
PREVIOUS = PARENT / "q20261011_n53_full_pair_orbits_accounted/measurement.json"
CANDIDATE = PRIOR / "candidates/IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirectISO0h7c80ef394c64.json"
INPUT_DIR = Path("/private/tmp/q1454_n53_inputs")
SOURCES = [Path(__file__), HERE / "indexcalc.py", HERE / "native_field53.hpp", HERE / "native_sweep.cpp",
           HERE / "build.py", HERE / "run.py", PRIOR / "probe_n53_relation.py",
           PARENT / "run_probe.py", PARENT / "enumerate_weight_base.py",
           PARENT / "chain_s3.py", Path(field.__file__), Path(curves.__file__)]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_inputs() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    stage = json.loads(STAGE.read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    previous = json.loads(PREVIOUS.read_text())
    candidate = json.loads(CANDIDATE.read_text())
    assert protocol["curve_id"] == stage["curve_id"] == archive["curve"]["curve_id"]
    assert protocol["workload_id"] == stage["workload_id"]
    assert protocol["isogeny"] == archive["isogeny"] == "none"
    assert protocol["factor_base_actual_B"] == archive["factor_base"]["actual_usable_points_B_before_folding"]
    assert protocol["factor_base_folded_columns_K"] == archive["factor_base"]["signed_frobenius_columns"]
    assert protocol["factor_base_enumerated_set_sha256"] == archive["factor_base"]["enumerated_set_sha256"]
    assert previous["curve_id"] == protocol["curve_id"]
    assert previous["factor_base_enumerated_set_sha256"] == protocol["factor_base_enumerated_set_sha256"]
    assert candidate["curve"]["subgroup_order"] == protocol["rank_accounting"]["modulus"]
    return {"protocol_sha256": sha(PROTOCOL), "stage_sha256": sha(STAGE),
            "archive_sha256": sha(ARCHIVE), "previous_sha256": sha(PREVIOUS),
            "candidate_sha256": sha(CANDIDATE),
            "sources_sha256": {str(path.relative_to(ROOT)): sha(path) for path in SOURCES},
            "public_target": stage["public_subgroup_target"],
            "python_version": platform.python_version()}


def factor_base_digest(onb, representatives) -> str:
    destinations = square_destinations(onb)
    keys = set()
    for representative in representatives:
        key = min(orbit(onb.toCoords(representative[0]), destinations))
        assert key not in keys
        keys.add(key)
    return hashlib.sha256(b"".join(key.to_bytes(7, "little")
                                   for key in sorted(keys))).hexdigest()


def write_points(path: Path, points) -> None:
    with path.open("wb") as stream:
        for point in points:
            for coordinate in point:
                stream.write(int(coordinate).to_bytes(16, "little"))


def export() -> dict:
    assert json.loads(FREEZE.read_text()) == frozen_inputs()
    assert not INPUT_DIR.exists()
    INPUT_DIR.mkdir()
    protocol = json.loads(PROTOCOL.read_text())
    stage = json.loads(STAGE.read_text())
    with gzip.open(ARCHIVE, "rt") as stream:
        archive = json.load(stream)
    r = protocol["rank_accounting"]["modulus"]
    started = time.perf_counter_ns()
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    target = tuple(map(int, stage["public_subgroup_target"]))
    assert curve.onCurve(target) and curve.mul(target, r) is None
    base, representatives, _ = base_and_columns(curve, onb, r,
                                                 int(archive["curve"]["cofactor"]))
    assert len(base) == protocol["factor_base_actual_B"]
    assert len(representatives) == protocol["factor_base_folded_columns_K"]
    assert factor_base_digest(onb, representatives) == protocol[
        "factor_base_enumerated_set_sha256"]
    base_setup_ns = time.perf_counter_ns() - started
    write_points(INPUT_DIR / "base.bin", base)
    write_points(INPUT_DIR / "representatives.bin", representatives)
    base_index = {point: index for index, point in enumerate(base)}
    assert len(base_index) == len(base)
    covered = set()
    with (INPUT_DIR / "representative_indices.bin").open("wb") as stream:
        for representative in representatives:
            stream.write(struct.pack("<H", base_index[representative]))
    with (INPUT_DIR / "lift_indices.bin").open("wb") as stream:
        for representative in representatives:
            point = representative
            for _ in range(53):
                negative = curve.neg(point)
                assert point in base_index and negative in base_index
                covered.add(point); covered.add(negative)
                stream.write(struct.pack("<HH", base_index[point], base_index[negative]))
                point = curve.frob(point)
            assert point == representative
    assert covered == set(base)
    pairs = [(i, j) for i in range(len(representatives))
             for j in range(i, len(representatives))]
    random.Random(protocol["point_decomposition"]["pair_block_seed"]).shuffle(pairs)
    with (INPUT_DIR / "blocks.bin").open("wb") as stream:
        for i, j in pairs:
            stream.write(struct.pack("<HH", i, j))
    query_rng = random.Random(protocol["point_decomposition"]["query_seed"])
    with (INPUT_DIR / "queries.bin").open("wb") as stream:
        for _ in range(protocol["point_decomposition"]["query_sample_cap"]):
            stream.write(struct.pack("<HH", query_rng.randrange(len(base)),
                                     query_rng.randrange(len(base))))
    elapsed_ns = time.perf_counter_ns() - started
    files = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size}
             for p in sorted(INPUT_DIR.iterdir()) if p.is_file()}
    receipt = {"proposal_id": "Q1454", "candidate_id": None, "run_id": None,
               "curve_id": protocol["curve_id"], "workload_id": protocol["workload_id"],
               "isogeny": "none", "factor_base_actual_B": len(base),
               "factor_base_folded_columns_K": len(representatives),
               "factor_base_enumerated_set_sha256": factor_base_digest(onb, representatives),
               "target_x_hex": format(target[0], "x"), "target_y_hex": format(target[1], "x"),
               "query_samples": protocol["point_decomposition"]["query_sample_cap"],
               "pair_blocks": len(pairs), "base_setup_ns": base_setup_ns,
               "total_export_ns": elapsed_ns, "files": files,
               "freeze_sha256": sha(FREEZE), "source_sha256": sha(Path(__file__))}
    (HERE / "export_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        assert not FREEZE.exists()
        FREEZE.write_text(json.dumps(frozen_inputs(), indent=2, sort_keys=True) + "\n")
        print("FROZEN", FREEZE)
    else:
        assert args.export and not (HERE / "export_receipt.json").exists()
        receipt = export()
        print("EXPORTED", receipt["files"])


if __name__ == "__main__":
    main()
