#!/usr/bin/env sage -python
"""Exact low-weight dual checks before N131 d13 pair-pivot solving."""

import hashlib
import importlib.util
import json
import resource
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_d13_batched_pair_inverse_20261009"
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"
CODEGEN = HERE.parents[2] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import field

spec = importlib.util.spec_from_file_location("batched_base", BASE / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

N, DIM, DOMAIN, CHECKS = 131, 13, 8192, 8


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def build_checks(rows):
    """Find eight independent parity checks of weight at most three per sum."""
    all_checks = [[]]
    weight_histogram = {}
    for s in range(1, DOMAIN):
        words = [word for _, word, _ in rows[s]]
        signatures = []
        by_signature = {}
        for bit in range(N):
            signature = sum(((word >> bit) & 1) << row
                            for row, word in enumerate(words))
            signatures.append(signature)
            by_signature.setdefault(signature, []).append(bit)
        selected = []
        independent = {}

        def add(mask):
            remainder = mask
            while remainder:
                leading = remainder.bit_length() - 1
                old = independent.get(leading)
                if old is None:
                    independent[leading] = remainder
                    selected.append(mask)
                    weight = mask.bit_count()
                    weight_histogram[weight] = weight_histogram.get(weight, 0) + 1
                    return len(selected) == CHECKS
                remainder ^= old
            return False

        for bit in by_signature.get(0, []):
            if add(1 << bit):
                break
        if len(selected) < CHECKS:
            for positions in by_signature.values():
                for j in positions[1:]:
                    if add((1 << positions[0]) | (1 << j)):
                        break
                if len(selected) == CHECKS:
                    break
        if len(selected) < CHECKS:
            for i in range(N):
                for j in range(i + 1, N):
                    complement = signatures[i] ^ signatures[j]
                    positions = by_signature.get(complement, ())
                    for k in positions:
                        if k > j and add((1 << i) | (1 << j) | (1 << k)):
                            break
                    if len(selected) == CHECKS:
                        break
                if len(selected) == CHECKS:
                    break
        if len(selected) != CHECKS:
            raise ValueError(f"sum {s} has only {len(selected)} low-weight dual checks")
        if any((mask & word).bit_count() & 1 for mask in selected for word in words):
            raise ValueError(f"sum {s} has an invalid dual check")
        all_checks.append(selected)
    return all_checks, weight_histogram


def inverse_with_checks(onb, rows, valid, squared_basis, checks, z_mask):
    terms = base.linear_terms(onb, squared_basis, z_mask)
    if terms is None:
        return [], 0, 0
    offset, columns = terms
    rhs_by_sum = [0] * DOMAIN
    rhs_by_sum[0] = offset
    found = set()
    rejects = solves = 0
    for s in range(1, DOMAIN):
        low = s & -s
        rhs = rhs_by_sum[s ^ low] ^ columns[low.bit_length() - 1]
        rhs_by_sum[s] = rhs
        coordinate = onb.toCoords(rhs)
        if any((coordinate & mask).bit_count() & 1 for mask in checks[s]):
            rejects += 1
            continue
        solves += 1
        base.add_pair(found, base.solve_rows(rows[s], coordinate), s, valid)
    return sorted(found), rejects, solves


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"run": HERE / "run.py", "audit": HERE / "audit.py",
             "base_run": BASE / "run.py", "base_protocol": BASE / "protocol.json",
             "base_result": BASE / "result.json", "base_audit": BASE / "audit.json",
             "field": CODEGEN / "field.py", "pivots": SOURCE / "pivots.bin",
             "valid_codes": SOURCE / "valid_codes.json",
             "runtime": HERE / "runtime_info.json"}
    if (protocol["status"] != "FROZEN" or
            any(sha(path) != protocol["source_sha256"][name]
                for name, path in paths.items()) or
            json.loads(paths["runtime"].read_text())["status"] != "verified"):
        raise ValueError("frozen source or checked Sage runtime changed")
    base_protocol = json.loads(paths["base_protocol"].read_text())
    if (protocol["inputs"] != base_protocol["inputs"] or
            protocol["repetitions"] != 2 or len(protocol["inputs"]) != 64):
        raise ValueError("paired input protocol changed")
    rows = base.read_index(paths["pivots"])
    valid = set(json.loads(paths["valid_codes"].read_text()))
    onb = field.Onb(N)
    squared_basis = [onb.sqr(onb.fromCoords(int(mask, 16)))
                     for mask in base_protocol["basis_masks_hex"]]
    setup_start = time.monotonic_ns()
    checks, weight_histogram = build_checks(rows)
    setup_ns = time.monotonic_ns() - setup_start
    first = protocol["inputs"][0]["z_mask"]
    if inverse_with_checks(onb, rows, valid, squared_basis, checks, first)[0] != \
            base.linear_dense(onb, rows, valid, squared_basis, first):
        raise ValueError("warm-up output mismatch")
    raw, saved_pairs = [], []
    start = time.monotonic_ns()
    for rep in range(protocol["repetitions"]):
        for i, item in enumerate(protocol["inputs"]):
            z_mask = item["z_mask"]
            order = ("linear_dense", "syndrome8") if (i + rep) % 2 == 0 else \
                    ("syndrome8", "linear_dense")
            outputs = {}
            for method in order:
                t0 = time.monotonic_ns()
                if method == "linear_dense":
                    outputs[method] = base.linear_dense(onb, rows, valid,
                                                        squared_basis, z_mask)
                    rejected = 0
                    solves = DOMAIN - 1
                else:
                    outputs[method], rejected, solves = inverse_with_checks(
                        onb, rows, valid, squared_basis, checks, z_mask)
                raw.append({"repetition": rep, "input_index": i,
                            "method": method, "wall_ns": time.monotonic_ns() - t0,
                            "syndrome_rejections": rejected, "pivot_solves": solves,
                            "pair_count": len(outputs[method])})
            if outputs["linear_dense"] != outputs["syndrome8"]:
                raise ValueError(f"pair mismatch on input {i}")
            if item["kind"] == "positive" and tuple(item["pair"]) not in outputs["syndrome8"]:
                raise ValueError(f"positive pair missing on input {i}")
            if rep == 0:
                saved_pairs.append([list(pair) for pair in outputs["syndrome8"]])
            if (time.monotonic_ns() - start >
                    protocol["wall_cap_seconds"] * 1_000_000_000 or
                    rss_bytes() > protocol["rss_cap_bytes"]):
                raise RuntimeError("frozen wall or RSS cap reached")
    by_key = {(row["repetition"], row["input_index"], row["method"]): row
              for row in raw}
    paired = [by_key[(rep, i, "linear_dense")]["wall_ns"] /
              by_key[(rep, i, "syndrome8")]["wall_ns"]
              for rep in range(2) for i in range(64)]
    receipt = {"kind": "n131_d13_sparse_dual_pair_inverse", "status": "PASS_EXACT_MATCH",
               "proposal_id": protocol["proposal_id"], "candidate_id": None,
               "run_id": None, "curve_id": protocol["curve_id"],
               "check_count_per_sum": CHECKS, "sum_count": DOMAIN - 1,
               "dual_weight_histogram": weight_histogram,
               "dual_index_setup_wall_ns": setup_ns,
               "dual_index_payload_bytes": (DOMAIN - 1) * CHECKS * 17,
               "input_pair_results": saved_pairs, "raw": raw,
               "method_wall_ns":
               {name: base.summary([row["wall_ns"] for row in raw if row["method"] == name])
                for name in ("linear_dense", "syndrome8")},
               "paired_linear_over_syndrome8":
               {"median": statistics.median(paired),
                "p10": statistics.quantiles(paired, n=10, method="inclusive")[0],
                "p90": statistics.quantiles(paired, n=10, method="inclusive")[-1],
                "min": min(paired), "max": max(paired)},
               "syndrome_rejections_total": sum(row["syndrome_rejections"] for row in raw
                                                if row["method"] == "syndrome8"),
               "pivot_solves_total": sum(row["pivot_solves"] for row in raw
                                         if row["method"] == "syndrome8"),
               "measurement_wall_ns": time.monotonic_ns() - start,
               "peak_process_rss_bytes": rss_bytes(),
               "source_sha256": {"protocol": sha(protocol_path),
                                 **{name: sha(path) for name, path in paths.items()}}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "dual_index_setup_wall_ns": setup_ns,
                      "dual_weight_histogram": weight_histogram,
                      "method_wall_ns": receipt["method_wall_ns"],
                      "paired_linear_over_syndrome8":
                      receipt["paired_linear_over_syndrome8"],
                      "pivot_solves_total": receipt["pivot_solves_total"]}))


if __name__ == "__main__":
    main()
