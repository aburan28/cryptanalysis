#!/usr/bin/env sage -python
"""Recover a d13 same-rotation pair seed sum from one joint linear S3 gate."""

import hashlib
import importlib.util
import json
import resource
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n131_d13_batched_pair_inverse_20261009"
DUAL = GOAL / "n131_d13_syndrome_pair_inverse_20261009"
SOURCE = GOAL / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import field


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("linear_batch_base", BASE / "run.py")
dual = load("sparse_dual_base", DUAL / "run.py")
source = load("same_rotation_source", SOURCE / "run.py")
N, DIM, DOMAIN = 131, 13, 8192


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def product_basis(onb, basis):
    w = [onb.add(onb.sqr(value), value) for value in basis]
    products = [onb.mul(w[i], w[j]) for i in range(DIM)
                for j in range(i, DIM)]
    rank = len(source.echelon([onb.toCoords(value) for value in products])[0])
    if len(products) != 91 or rank != 91:
        raise ValueError("frozen d13 pair-product span lost rank 91")
    return products


def joint_inverse(onb, rows, valid, squared_basis, products, z_mask):
    z = onb.fromCoords(z_mask)
    z_squared = onb.sqr(z)
    az = onb.add(z_squared, z)
    if az == 0:
        return [], {"rank": None, "status": "EXCEPTIONAL_EMPTY", "sum": None}
    columns = [onb.toCoords(value) for value in squared_basis]
    columns += [onb.toCoords(onb.mul(az, value)) for value in products]
    pivots, kernel = source.echelon(columns)
    rank = len(pivots)
    if rank < DIM + len(products):
        return base.linear_dense(onb, rows, valid, squared_basis, z_mask), {
            "rank": rank, "status": "RANK_FALLBACK", "sum": None,
            "nullity": len(kernel)}
    coefficients = source.solve(pivots, onb.toCoords(z_squared))
    if coefficients is None:
        return [], {"rank": rank, "status": "SPAN_REJECT", "sum": None}
    s = coefficients & (DOMAIN - 1)
    if s == 0:
        return [], {"rank": rank, "status": "ZERO_SUM_REJECT", "sum": 0}
    s_squared = 0
    for bit in range(DIM):
        if (s >> bit) & 1:
            s_squared ^= squared_basis[bit]
    quotient = onb.mul(onb.add(s_squared, z_squared), onb.inv(az))
    code = base.solve_rows(rows[s], onb.toCoords(quotient))
    found = set()
    base.add_pair(found, code, s, valid)
    return sorted(found), {"rank": rank,
                           "status": "PAIR" if found else "FIXED_SUM_REJECT",
                           "sum": s}


def main():
    result_path = HERE / "result.json"
    if result_path.exists():
        raise FileExistsError(result_path)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "freeze": HERE / "freeze.py", "field": CODEGEN / "field.py",
             "base_run": BASE / "run.py", "base_result": BASE / "result.json",
             "dual_run": DUAL / "run.py", "dual_result": DUAL / "result.json",
             "source_run": SOURCE / "run.py", "source_result": SOURCE / "result.json",
             "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "runtime": HERE / "runtime_info.json"}
    if (protocol["status"] != "FROZEN" or
            any(sha(path) != protocol["source_sha256"][name]
                for name, path in paths.items()) or
            json.loads(paths["runtime"].read_text())["status"] != "verified"):
        raise ValueError("frozen source or checked Sage runtime changed")
    onb = field.Onb(N)
    rows = base.read_index(paths["pivots"])
    valid = set(json.loads(paths["valid_codes"].read_text()))
    basis = [onb.fromCoords(int(mask, 16)) for mask in protocol["basis_masks_hex"]]
    squared_basis = [onb.sqr(value) for value in basis]
    setup_start = time.monotonic_ns()
    products = product_basis(onb, basis)
    checks, histogram = dual.build_checks(rows)
    setup_ns = time.monotonic_ns() - setup_start
    inputs = protocol["inputs"]
    if len(inputs) != 72 or protocol["repetitions"] != 2:
        raise ValueError("frozen input shape changed")
    raw = []
    pair_results = []
    start = time.monotonic_ns()
    for rep in range(2):
        for i, item in enumerate(inputs):
            z_mask = item["z_mask"]
            order = ("syndrome8", "joint_linear") if (i + rep) % 2 == 0 else \
                    ("joint_linear", "syndrome8")
            outputs = {}
            detail = None
            for method in order:
                t0 = time.monotonic_ns()
                if method == "syndrome8":
                    outputs[method], rejected, solves = dual.inverse_with_checks(
                        onb, rows, valid, squared_basis, checks, z_mask)
                    method_detail = {"syndrome_rejections": rejected,
                                     "pivot_solves": solves}
                else:
                    outputs[method], detail = joint_inverse(
                        onb, rows, valid, squared_basis, products, z_mask)
                    method_detail = detail
                raw.append({"repetition": rep, "input_index": i,
                            "method": method, "wall_ns": time.monotonic_ns() - t0,
                            "pair_count": len(outputs[method]),
                            "detail": method_detail})
            if outputs["joint_linear"] != outputs["syndrome8"]:
                raise ValueError(f"exact pair-set mismatch on input {i}")
            if item["kind"] == "positive" and tuple(item["pair"]) not in outputs["joint_linear"]:
                raise ValueError(f"positive pair missing on input {i}")
            if rep == 0:
                pair_results.append({"input_index": i, "kind": item["kind"],
                                     "z_mask": z_mask, "pairs":
                                     [list(pair) for pair in outputs["joint_linear"]],
                                     "joint_detail": detail})
            if (time.monotonic_ns() - start >
                    protocol["wall_cap_seconds"] * 1_000_000_000 or
                    rss_bytes() > protocol["rss_cap_bytes"]):
                raise RuntimeError("frozen query wall or RSS cap reached")
    by_key = {(row["repetition"], row["input_index"], row["method"]): row
              for row in raw}
    ratios = [by_key[(rep, i, "syndrome8")]["wall_ns"] /
              by_key[(rep, i, "joint_linear")]["wall_ns"]
              for rep in range(2) for i in range(len(inputs))]
    rank_histogram = {}
    status_histogram = {}
    for item in pair_results:
        detail = item["joint_detail"]
        key = str(detail["rank"])
        rank_histogram[key] = rank_histogram.get(key, 0) + 1
        status = detail["status"]
        status_histogram[status] = status_histogram.get(status, 0) + 1
    receipt = {"kind": "n131_d13_joint_linear_sum_recovery", "status": "PASS_EXACT_MATCH",
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "run_id": None, "curve_id": protocol["curve_id"],
               "product_span_rank": len(products), "joint_column_count": 104,
               "setup_wall_ns": setup_ns, "dual_weight_histogram": histogram,
               "rank_histogram": rank_histogram,
               "status_histogram": status_histogram,
               "input_pair_results": pair_results, "raw": raw,
               "method_wall_ns": {name: base.summary([row["wall_ns"] for row in raw
                                                       if row["method"] == name])
                                  for name in ("syndrome8", "joint_linear")},
               "paired_syndrome_over_joint":
               {"median": statistics.median(ratios),
                "p10": statistics.quantiles(ratios, n=10, method="inclusive")[0],
                "p90": statistics.quantiles(ratios, n=10, method="inclusive")[-1],
                "min": min(ratios), "max": max(ratios)},
               "measurement_wall_ns": time.monotonic_ns() - start,
               "peak_process_rss_bytes": rss_bytes(),
               "source_sha256": {"protocol": sha(protocol_path),
                                 **{name: sha(path) for name, path in paths.items()}}}
    result_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "rank_histogram": rank_histogram,
                      "status_histogram": status_histogram,
                      "method_wall_ns": receipt["method_wall_ns"],
                      "paired_syndrome_over_joint":
                      receipt["paired_syndrome_over_joint"]}))


if __name__ == "__main__":
    main()
