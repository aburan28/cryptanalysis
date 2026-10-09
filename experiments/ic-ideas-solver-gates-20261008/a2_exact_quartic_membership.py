#!/usr/bin/env python3
"""Test whether quartic equations characterize the N23 sparse-sum set exactly."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from sage.all import GF

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from a2_membership_degree import family  # noqa: E402
from a2_quartic_relations import columns_at, evaluation  # noqa: E402

PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"


def polynomial_truth(masks):
    data = np.zeros(1 << 23, dtype=np.uint8)
    data[masks] = 1
    for bit in range(23):
        stride = 1 << bit
        blocks = data.reshape((-1, 2 * stride))
        blocks[:, stride:] ^= blocks[:, :stride]
    return data


def main():
    out = HERE / "a2_exact_quartic_membership.json"
    equations_path = HERE / "a2_exact_quartic_equations.json.gz"
    if out.exists() or equations_path.exists():
        raise FileExistsError("preserve prior exact membership artifacts")
    started = time.perf_counter_ns()
    prior = json.loads(PRIOR.read_text())
    _, values = family(prior["gamma_bits"], prior["field_modulus_bits"])
    columns = columns_at(4)
    M = evaluation(values, columns)
    rank = int(M.rank())
    assert rank == 7614 and len(columns) == 10903
    kernel = M.right_kernel().basis_matrix()
    assert kernel.nrows() == len(columns)-rank
    expected = np.zeros(1 << 23, dtype=np.bool_)
    expected[values] = True
    candidates = np.ones(1 << 23, dtype=np.bool_)
    selected = []
    progress = []
    max_equations = min(256, kernel.nrows())
    for i in range(max_equations):
        masks = [columns[j] for j in range(kernel.ncols()) if kernel[i, j]]
        assert masks and max(mask.bit_count() for mask in masks) == 4
        candidates &= polynomial_truth(masks) == 0
        selected.append(masks)
        if i+1 in (1, 8, 16, 32, 48, 64, 96, 128, 192, 256) or not np.any(candidates & ~expected):
            remaining = int(np.count_nonzero(candidates & ~expected))
            progress.append({"equations": i+1,
                             "candidate_count": int(np.count_nonzero(candidates)),
                             "false_positives": remaining})
            print(json.dumps(progress[-1]), flush=True)
            if remaining == 0:
                break
    exact = np.array_equal(candidates, expected)
    encoded = json.dumps(selected, separators=(",", ":")).encode()
    equations_path.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "sparse_sum_count": len(values),
              "domain_size": 1 << 23,
              "quartic_evaluation_rank": rank,
              "quartic_vanishing_space_dimension": int(kernel.nrows()),
              "selected_equation_count": len(selected),
              "selected_total_anf_terms": sum(len(row) for row in selected),
              "exact_membership_over_all_field_elements": exact,
              "remaining_false_positives": int(np.count_nonzero(candidates & ~expected)),
              "progress": progress,
              "equations_artifact": equations_path.name,
              "equations_uncompressed_sha256": hashlib.sha256(encoded).hexdigest(),
              "equations_gzip_sha256": hashlib.sha256(equations_path.read_bytes()).hexdigest(),
              "membership_truth_sha256": hashlib.sha256(expected.tobytes()).hexdigest(),
              "stage_wall_ns_exploratory": time.perf_counter_ns()-started,
              "prior_receipt_sha256": hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"equations": len(selected), "exact": exact,
                      "false_positives": answer["remaining_false_positives"]}))


if __name__ == "__main__":
    main()
