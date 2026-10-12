#!/usr/bin/env python3
"""Build a resumable, complete n83 two-G point-witness quotient index.

The large row files live outside Git.  This stage supplies witnesses for
unknown point complements; the scalar-support count alone cannot do that.
"""

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

import numpy as np

import curves
import field
from dyadic_base_geometry import enumerate_points
from dyadic_n83_compact_index import PackedIndex, ROW_DTYPE, encode_key
from perf_probe import sha
from x_only_cycle import XOnlyCycle

HERE = Path(__file__).resolve().parent
PROPOSAL_ID = "Q1029"
ORBIT_SIZE = 166


def frozen(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_sorted(rows):
    """Count unique keys and hash first witnesses without a second giant array."""
    key_digest = hashlib.sha256()
    row_digest = hashlib.sha256()
    key_digest.update(b"[")
    previous = None
    count = 0
    for start in range(0, len(rows), 1 << 20):
        block = rows[start:start + (1 << 20)]
        mask = np.empty(len(block), dtype=np.bool_)
        mask[0] = previous is None or (
            int(block["hi"][0]), int(block["lo"][0])) != previous
        mask[1:] = ((block["hi"][1:] != block["hi"][:-1]) |
                    (block["lo"][1:] != block["lo"][:-1]))
        unique = block[mask]
        row_digest.update(unique.tobytes())
        for row in unique:
            if count:
                key_digest.update(b",")
            key = ((int(row["hi"]) << 64) | int(row["lo"])) - 1
            key_digest.update(str(key).encode())
            count += 1
        previous = int(block["hi"][-1]), int(block["lo"][-1])
    key_digest.update(b"]")
    return count, key_digest.hexdigest(), row_digest.hexdigest()


def main(window, workdir):
    if window < 1 or window > 1000:
        raise ValueError("supported windows are 1..1000")
    workdir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = workdir / "checkpoint.json"
    raw_path = workdir / "rows.raw"
    sorted_path = workdir / "rows.sorted"
    receipt_path = HERE / "runs" / f"n83_dyadic_G_pair_witness_index_L{window}.json"
    reference_path = HERE / "runs" / "n83_perf_prefix.json"
    geometry_path = HERE / "runs" / "n83_dyadic_target_seed_geometry.json"
    reference = json.loads(reference_path.read_text())
    geometry = json.loads(geometry_path.read_text())
    assert reference["curve_id"] == geometry["curve_id"]
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    generator = tuple(reference["curve_identity_record"]["curve"]["generator"])
    target = tuple(reference["workload"]["target"])
    order = int(reference["subgroup_order"])
    eigenvalue = int(geometry["frobenius_eigenvalue_mod_r"])
    assert curve.mul(generator, eigenvalue) == curve.frob(generator)
    started = time.perf_counter()
    labels, representatives, digests = enumerate_points(
        curve, onb, [generator, target], window, eigenvalue, order)
    base_seconds = time.perf_counter() - started
    assert len(labels) == 2 * ORBIT_SIZE * window
    left_reps = [point for point in sorted(representatives)
                 if labels[point][0] == 0]
    right_base = [point for point in sorted(labels) if labels[point][0] == 0]
    assert len(left_reps) == window and len(right_base) == ORBIT_SIZE * window
    canonicalize = XOnlyCycle(onb)
    orbit_keys = [canonicalize.key_and_shift(curve, point)[0]
                  for point in left_reps]
    assert len(set(orbit_keys)) == window
    orbit_number = {key: i for i, key in enumerate(orbit_keys)}
    buckets = [[] for _ in left_reps]
    for right_index, point in enumerate(right_base):
        key = canonicalize.key_and_shift(curve, point)[0]
        buckets[orbit_number[key]].append(right_index)
    assert all(len(bucket) == ORBIT_SIZE for bucket in buckets)
    generators = 83 * window * (window + 1)
    expected_bytes = generators * ROW_DTYPE.itemsize
    workload = {
        "curve_id": reference["curve_id"], "target": target,
        "target_count": 1, "doubling_window": window,
        "stage": "complete unordered two-G point-witness quotient index",
        "quotient": "signed Frobenius of order 166",
    }
    workload_id = hashlib.sha256(frozen(workload)).hexdigest()[:12]
    identity = {"curve_id": reference["curve_id"], "workload_id": workload_id,
                "window": window, "source_sha256": sha(Path(__file__)),
                "factor_base_sha256": digests["enumerated_set_sha256"],
                "generators": generators, "row_bytes": ROW_DTYPE.itemsize}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text())
        assert checkpoint["identity"] == identity
        assert raw_path.stat().st_size == expected_bytes
    else:
        if raw_path.exists() or sorted_path.exists():
            raise RuntimeError("row file exists without matching checkpoint")
        checkpoint = {"identity": identity, "completed_left": 0,
                      "completed_rows": 0, "build_seconds": 0.0,
                      "phase": "building"}
        rows = np.memmap(raw_path, dtype=ROW_DTYPE, mode="w+",
                         shape=(generators,))
        rows.flush()
        del rows
        write_json(checkpoint_path, checkpoint)
    if checkpoint["phase"] == "building":
        rows = np.memmap(raw_path, dtype=ROW_DTYPE, mode="r+",
                         shape=(generators,))
        at = checkpoint["completed_rows"]
        build_started = time.perf_counter()
        for left_index in range(checkpoint["completed_left"], window):
            left = left_reps[left_index]
            for bucket in buckets[left_index:]:
                for right_index in bucket:
                    total = curve.add(left, right_base[right_index])
                    key, shift = canonicalize.key_and_shift(curve, total)
                    hi, lo = encode_key(key)
                    witness = (left_index * len(right_base) + right_index) * 83 + shift
                    rows[at] = (hi, lo, witness)
                    at += 1
            rows.flush()
            checkpoint.update(completed_left=left_index + 1,
                              completed_rows=at,
                              build_seconds=checkpoint["build_seconds"] +
                              time.perf_counter() - build_started)
            write_json(checkpoint_path, checkpoint)
            build_started = time.perf_counter()
            if (left_index + 1) % max(1, min(100, window // 10)) == 0:
                print(json.dumps({"completed_left": left_index + 1,
                                  "completed_rows": at,
                                  "build_seconds": checkpoint["build_seconds"]}),
                      flush=True)
        assert at == generators
        del rows
        checkpoint["phase"] = "built"
        write_json(checkpoint_path, checkpoint)
    if checkpoint["phase"] == "built":
        raw = np.memmap(raw_path, dtype=ROW_DTYPE, mode="r",
                        shape=(generators,))
        sort_started = time.perf_counter()
        ordered = np.sort(raw, order=["hi", "lo"], kind="quicksort")
        sorted_rows = np.memmap(sorted_path, dtype=ROW_DTYPE, mode="w+",
                                shape=(generators,))
        sorted_rows[:] = ordered
        sorted_rows.flush()
        del raw, ordered, sorted_rows
        checkpoint["sort_seconds"] = time.perf_counter() - sort_started
        checkpoint["phase"] = "sorted"
        write_json(checkpoint_path, checkpoint)
    assert checkpoint["phase"] in ("sorted", "complete")
    rows = np.memmap(sorted_path, dtype=ROW_DTYPE, mode="r",
                     shape=(generators,))
    unique_count, key_digest, retained_digest = scan_sorted(rows)
    if window == 32:
        control_path = HERE / "runs" / "n83_dyadic_five_sum_symmetric_stage.json"
        control = json.loads(control_path.read_text())
        assert unique_count == control["build"]["quotient_keys"]
        assert key_digest == control["build"]["key_sha256"]
        assert retained_digest == control["build"]["retained_array_sha256"]
    if window == 1000:
        support_path = HERE / "runs" / "n83_dyadic_G_pair_scalar_support_L1000.json"
        support = json.loads(support_path.read_text())
        assert digests["enumerated_set_sha256"] == support[
            "factor_base"]["enumerated_set_sha256"]
        assert unique_count == support["L1000_exact_quotient_keys"]
    index = PackedIndex(rows, left_reps, right_base, curve, canonicalize)
    rng = random.Random(202609281029 + window)
    samples = sorted(set([0, generators - 1] +
                         [rng.randrange(generators) for _ in range(1000)]))
    for pos in samples:
        row = rows[pos]
        key = ((int(row["hi"]) << 64) | int(row["lo"])) - 1
        representative, pair = index.decode(row)
        assert curve.add(*pair) == representative
        assert canonicalize.key_and_shift(curve, representative) == (key, 0)
    sorted_sha = hash_file(sorted_path)
    receipt = {
        "kind": "n83_two_G_complete_point_witness_quotient_index",
        "scope": "complete point-witness index and sampled witness controls; no ordinary relation or DLP",
        "proposal_id": PROPOSAL_ID, "candidate_id": None,
        "run_id": f"{PROPOSAL_ID}W{workload_id}R1",
        "workload_id": workload_id, "workload": workload,
        "curve_id": reference["curve_id"],
        "curve_identity_record": reference["curve_identity_record"],
        "isogeny": "none", "endomorphism_order_conductor": None,
        "factor_base": {"actual_usable_points_B_before_folding": len(labels),
                        "signed_frobenius_columns": len(representatives),
                        "effective_unknown_log_columns_after_dyadic_labels": 1,
                        **digests},
        "G_side_actual_points": len(right_base),
        "unordered_pair_orbit_generators": generators,
        "quotient_keys": unique_count,
        "index_row_bytes": ROW_DTYPE.itemsize,
        "raw_array_bytes": expected_bytes,
        "sorted_array_sha256": sorted_sha,
        "retained_unique_row_sha256": retained_digest,
        "key_sha256": key_digest,
        "sampled_witness_replays": len(samples),
        "base_seconds": base_seconds,
        "build_seconds": checkpoint["build_seconds"],
        "sort_seconds": checkpoint["sort_seconds"],
        "complete_work_log2": None,
        "verified_single_target_dlp": False,
        "source_sha256": identity["source_sha256"],
        "dependency_sha256": {name: sha(HERE / name) for name in (
            "dyadic_base_geometry.py", "dyadic_n83_compact_index.py",
            "x_only_cycle.py", "curves.py", "field.py")},
        "reference_sha256": sha(reference_path),
        "geometry_sha256": sha(geometry_path),
        "local_sorted_rows": str(sorted_path),
        "local_checkpoint": str(checkpoint_path),
    }
    write_json(receipt_path, receipt)
    checkpoint["phase"] = "complete"
    write_json(checkpoint_path, checkpoint)
    print(json.dumps({"window": window, "quotient_keys": unique_count,
                      "generators": generators, "build_seconds": receipt["build_seconds"],
                      "sort_seconds": receipt["sort_seconds"],
                      "sorted_array_sha256": sorted_sha}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    main(args.window, args.workdir)
