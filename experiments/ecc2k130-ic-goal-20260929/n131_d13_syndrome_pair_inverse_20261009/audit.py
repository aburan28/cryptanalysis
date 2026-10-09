#!/usr/bin/env sage -python
"""Audit every dual check and the complete paired comparison receipt."""

import hashlib
import importlib.util
import json
import statistics
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "n131_d13_batched_pair_inverse_20261009"
SOURCE = HERE.parent / "n131_d13_same_rotation_pairs_20261009"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path = HERE / "protocol.json", HERE / "result.json"
    protocol, result = json.loads(protocol_path.read_text()), json.loads(result_path.read_text())
    if (protocol["status"] != "FROZEN" or result["status"] != "PASS_EXACT_MATCH" or
            result["source_sha256"]["protocol"] != sha(protocol_path)):
        raise ValueError("frozen protocol or result changed")
    for name, digest in protocol["source_sha256"].items():
        path = {"run": HERE / "run.py", "audit": HERE / "audit.py",
                "base_run": BASE / "run.py", "base_protocol": BASE / "protocol.json",
                "base_result": BASE / "result.json", "base_audit": BASE / "audit.json",
                "field": HERE.parents[2] / "ecc2k130/codegen/field.py",
                "pivots": SOURCE / "pivots.bin",
                "valid_codes": SOURCE / "valid_codes.json",
                "runtime": HERE / "runtime_info.json"}[name]
        if sha(path) != digest:
            raise ValueError(f"frozen source changed: {name}")
    runner = load("syndrome_runner", HERE / "run.py")
    base = load("batched_audit_base", BASE / "run.py")
    rows = base.read_index(SOURCE / "pivots.bin")
    checks, histogram = runner.build_checks(rows)
    if histogram != {int(k): value for k, value in result["dual_weight_histogram"].items()}:
        raise ValueError("dual weight histogram changed")
    checked = 0
    for s in range(1, 8192):
        group = [word for _, word, _ in rows[s]]
        if len(checks[s]) != 8:
            raise ValueError("wrong dual check count")
        basis = {}
        for mask in checks[s]:
            if mask.bit_count() > 3 or any((mask & word).bit_count() & 1 for word in group):
                raise ValueError("dual mask does not annihilate image")
            remainder = mask
            while remainder:
                leading = remainder.bit_length() - 1
                if leading not in basis:
                    basis[leading] = remainder
                    break
                remainder ^= basis[leading]
            else:
                raise ValueError("dependent dual checks")
            checked += 1
    sage_rank_checks = 0
    for s in (1, 2, 3, 7, 31, 127, 1023, 2047, 4095, 8191):
        mat = matrix(GF(2), 8, 131,
                     lambda row, col: (checks[s][row] >> col) & 1)
        if mat.rank() != 8:
            raise ValueError("Sage dual matrix rank differs")
        sage_rank_checks += 1
    old = json.loads((BASE / "result.json").read_text())
    if result["input_pair_results"] != [item["pairs"] for item in old["input_pair_results"]]:
        raise ValueError("syndrome output differs from independently replayed prior output")
    raw = result["raw"]
    if len(raw) != 2 * 64 * 2:
        raise ValueError("raw timing row count changed")
    cells = {(row["repetition"], row["input_index"], row["method"]): row for row in raw}
    if len(cells) != len(raw):
        raise ValueError("duplicate raw timing cell")
    for rep in range(2):
        for i in range(64):
            baseline = cells[(rep, i, "linear_dense")]
            improved = cells[(rep, i, "syndrome8")]
            if (baseline["pivot_solves"] != 8191 or
                    improved["pivot_solves"] + improved["syndrome_rejections"] != 8191 or
                    baseline["pair_count"] != improved["pair_count"] or
                    improved["pair_count"] != len(result["input_pair_results"][i]) or
                    baseline["wall_ns"] <= 0 or improved["wall_ns"] <= 0):
                raise ValueError("invalid complete-sum comparison row")
    ratios = [cells[(rep, i, "linear_dense")]["wall_ns"] /
              cells[(rep, i, "syndrome8")]["wall_ns"]
              for rep in range(2) for i in range(64)]
    if statistics.median(ratios) != result["paired_linear_over_syndrome8"]["median"]:
        raise ValueError("paired median differs from raw rows")
    receipt = {"kind": "n131_d13_sparse_dual_pair_inverse_audit",
               "status": "PASS_ALL_DUALS_AND_MATCHED_OUTPUTS", "candidate_id": None,
               "run_id": None, "dual_masks_checked": checked,
               "sage_rank_checks": sage_rank_checks,
               "matched_inputs_checked": 64, "timing_rows_checked": len(raw),
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "audit": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "dual_masks_checked": checked,
                      "sage_rank_checks": sage_rank_checks}))


if __name__ == "__main__":
    main()
