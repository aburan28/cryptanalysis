#!/usr/bin/env python3
"""Extract and challenge the N23 sparse-sum quartic vanishing space."""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import sys
import time
from pathlib import Path

from sage.all import GF, matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from a2_membership_degree import family  # noqa: E402

PRIOR = HERE.parent / "ic-ideas-20261007/results/a2_final.json"


def columns_at(degree):
    return [sum(1 << i for i in subset)
            for d in range(degree + 1)
            for subset in itertools.combinations(range(23), d)]


def evaluation(values, columns):
    position = {mask: j for j, mask in enumerate(columns)}
    M = matrix(GF(2), len(values), len(columns))
    for row_index, value in enumerate(values):
        support = [i for i in range(23) if value >> i & 1]
        for degree in range(5):
            for subset in itertools.combinations(support, degree):
                M[row_index, position[sum(1 << i for i in subset)]] = 1
    return M


def row_rejection(syndrome):
    return sum(not syndrome[i].is_zero() for i in range(syndrome.nrows()))


def main():
    out = HERE / "a2_quartic_relations.json"
    if out.exists():
        raise FileExistsError(out)
    started = time.perf_counter_ns()
    prior = json.loads(PRIOR.read_text())
    powers, values = family(prior["gamma_bits"], prior["field_modulus_bits"])
    columns = columns_at(4)
    M = evaluation(values, columns)
    degree_ranks = {}
    for degree in range(5):
        width = len(columns_at(degree))
        degree_ranks[str(degree)] = int(M[:, :width].rank())
    K = M.right_kernel().basis_matrix()
    assert K.nrows() == len(columns) - degree_ranks["4"]
    assert (M * K[:32, :].transpose()).is_zero()
    rng = random.Random(20261008)
    value_set = set(values)
    random_outside = []
    while len(random_outside) < 1024:
        value = rng.randrange(1 << 23)
        if value not in value_set:
            random_outside.append(value)
    four_sum = []
    for subset in itertools.combinations(range(47), 4):
        value = 0
        for index in subset:
            value ^= powers[index]
        if value not in value_set:
            four_sum.append(value)
        if len(four_sum) == 1024:
            break
    samples = random_outside + four_sum
    S = evaluation(samples, columns)
    batches = []
    for count in (1, 8, 32, 128, K.nrows()):
        syndrome = S * K[:count, :].transpose()
        batches.append({"quartic_equations": count,
                        "uniform_outside_rejected": row_rejection(syndrome[:1024, :]),
                        "weight_four_sums_rejected": row_rejection(syndrome[1024:, :])})
    basis_weights = [int(K[i].hamming_weight()) for i in range(min(128, K.nrows()))]
    relation_masks = [[columns[j] for j in range(K.ncols()) if K[i, j]]
                      for i in range(min(3, K.nrows()))]
    answer = {"schema_version": 1, "proposal_id": "A2",
              "candidate_id": None, "run_id": None,
              "field_degree": 23, "sparse_sum_count": len(values),
              "evaluation_rows": M.nrows(), "degree_four_columns": M.ncols(),
              "evaluation_rank_by_degree": degree_ranks,
              "quartic_vanishing_space_dimension": K.nrows(),
              "first_128_kernel_basis_weight_range":
                  [min(basis_weights), max(basis_weights)],
              "first_three_quartic_polynomials_monomial_masks": relation_masks,
              "challenge_sample_sizes": {"uniform_outside": len(random_outside),
                                         "weight_four_sums": len(four_sum)},
              "challenge_results": batches,
              "sample_seed": 20261008,
              "stage_wall_ns_exploratory": time.perf_counter_ns() - started,
              "prior_receipt_sha256": hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    out.write_text(json.dumps(answer, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"rank_by_degree": degree_ranks,
                      "quartic_nullity": K.nrows(),
                      "challenge": batches}))


if __name__ == "__main__":
    main()
