#!/usr/bin/env python3
"""Finish the exact N23 quartic membership test on residual x values."""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from a2_membership_degree import family  # noqa: E402
from a2_quartic_relations import columns_at, evaluation  # noqa: E402

PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = HERE / "a2_full_quartic_audit.json"
    artifact = HERE / "a2_final_quartic_equations.json.gz"
    if out.exists() or artifact.exists():
        raise FileExistsError("preserve prior quartic audit artifacts")
    started = time.perf_counter_ns()
    prior = json.loads(PRIOR.read_text())
    _, values = family(prior["gamma_bits"], prior["field_modulus_bits"])
    residual_path = HERE / "a2_partial_false_positives.json"
    residual = json.loads(residual_path.read_text())["false_positive_x_bits"]
    assert len(residual) == 53 and not set(residual).intersection(values)
    source_artifact = HERE / "a2_exact_quartic_equations.json.gz"
    selected = json.loads(gzip.decompress(source_artifact.read_bytes()))
    assert len(selected) == 256
    columns = columns_at(4)
    M = evaluation(values, columns)
    rank = int(M.rank())
    assert rank == 7614
    kernel = M.right_kernel().basis_matrix()
    assert kernel.nrows() == 3289
    S = evaluation(residual, columns)
    syndrome = S * kernel.transpose()
    full_space_survivors = [residual[i] for i in range(len(residual))
                            if syndrome[i].is_zero()]
    uncovered = set(range(len(residual)))
    greedy = []
    while uncovered:
        best = max(range(kernel.nrows()),
                   key=lambda j: sum(bool(syndrome[i, j]) for i in uncovered))
        covered = {i for i in uncovered if syndrome[i, best]}
        if not covered:
            break
        greedy.append((best, len(covered)))
        uncovered -= covered
    added = [[columns[j] for j in range(kernel.ncols()) if kernel[index, j]]
             for index, _ in greedy]
    if greedy:
        chosen = matrix(GF(2), [kernel.row(index) for index, _ in greedy])
        assert (M * chosen.transpose()).is_zero()
    selected.extend(added)
    encoded = json.dumps(selected, separators=(",", ":")).encode()
    artifact.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "sparse_sum_count": len(values),
              "degree_four_evaluation_rank": rank,
              "degree_four_vanishing_space_dimension": int(kernel.nrows()),
              "partial_equations": 256, "partial_false_positives": len(residual),
              "full_space_survivors": full_space_survivors,
              "greedy_added_equations": len(added),
              "greedy_coverage": [{"kernel_basis_index": int(index),
                                   "newly_rejected": count}
                                  for index, count in greedy],
              "final_equation_count": len(selected),
              "final_total_anf_terms": sum(len(row) for row in selected),
              "final_false_positives": len(uncovered),
              "exact_membership_over_all_field_elements": not uncovered,
              "equations_artifact": artifact.name,
              "equations_uncompressed_sha256": hashlib.sha256(encoded).hexdigest(),
              "equations_gzip_sha256": sha(artifact),
              "stage_wall_ns_exploratory": time.perf_counter_ns()-started,
              "partial_residual_receipt_sha256": sha(residual_path),
              "partial_equations_sha256": sha(source_artifact),
              "source_sha256": sha(Path(__file__))}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"full_space_survivors": len(full_space_survivors),
                      "added_equations": len(added),
                      "final_false_positives": len(uncovered)}))


if __name__ == "__main__":
    main()
