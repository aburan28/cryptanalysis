"""Independent GF(2^131) replay of the all-seed product-span inverse."""

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
N = 131
MOD = (1 << 131) | (1 << 13) | (1 << 2) | (1 << 1) | 1
SEED_BITS = 18
BRANCH_BIT = 18
RHS_BIT = 19


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reduce_poly(value):
    while value.bit_length() > N:
        value ^= MOD << (value.bit_length() - N - 1)
    return value


def multiply(left, right):
    expanded = 0
    position = 0
    while right:
        if right & 1:
            expanded ^= left << position
        right >>= 1
        position += 1
    return reduce_poly(expanded)


def square(value):
    expanded = 0
    position = 0
    while value:
        if value & 1:
            expanded ^= 1 << (2 * position)
        value >>= 1
        position += 1
    return reduce_poly(expanded)


def inverse(value):
    assert value
    result = value
    for _ in range(N - 2):
        result = multiply(square(result), value)
    result = square(result)
    assert multiply(value, result) == 1
    return result


def halftrace(value):
    total = value
    power = value
    for _ in range((N - 1) // 2):
        power = square(square(power))
        total ^= power
    return total


def field_word(encoded):
    assert len(encoded) == 3
    value = sum(int(word) << (64 * index) for index, word in enumerate(encoded))
    assert 0 <= value < (1 << N)
    return value


def span_solutions(constant, columns, trace_constant, trace_columns):
    rows = []
    for coordinate in range(N):
        if 2 <= coordinate <= 36:
            continue
        row = ((constant >> coordinate) & 1) << RHS_BIT
        for variable, value in enumerate(columns):
            row ^= ((value >> coordinate) & 1) << variable
        rows.append(row)
    trace_row = trace_constant << RHS_BIT
    for variable, value in enumerate(trace_columns):
        trace_row ^= value << variable
    rows.append(trace_row)
    pivots = {}
    rank = 0
    for variable in range(BRANCH_BIT, -1, -1):
        pivot = next((row for row in range(rank, len(rows))
                      if rows[row] & (1 << variable)), None)
        if pivot is None:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        for row in range(len(rows)):
            if row != rank and rows[row] & (1 << variable):
                rows[row] ^= rows[rank]
        pivots[variable] = rank
        rank += 1
    if any(row == (1 << RHS_BIT) for row in rows[rank:]):
        return rank, False, []
    fixed = sum(((rows[row] >> RHS_BIT) & 1) << variable
                for variable, row in pivots.items())
    free = [variable for variable in range(BRANCH_BIT + 1) if variable not in pivots]
    nullspace = []
    for variable in free:
        vector = 1 << variable
        for pivot_variable, row in pivots.items():
            vector ^= ((rows[row] >> variable) & 1) << pivot_variable
        nullspace.append(vector)
    solutions = []
    for mask in range(1 << len(nullspace)):
        value = fixed
        for index, vector in enumerate(nullspace):
            if mask & (1 << index):
                value ^= vector
        solutions.append(value)
    return rank, True, solutions


def recover_masks(seed_mask, product, basis):
    seed = seed_mask << 1
    pivots = {}
    kernel = None
    for index, element in enumerate(basis):
        value = square(element) ^ multiply(seed, element)
        represented = 1 << index
        while value:
            leading = value.bit_length() - 1
            if leading not in pivots:
                pivots[leading] = (value, represented)
                break
            pivot_value, pivot_mask = pivots[leading]
            value ^= pivot_value
            represented ^= pivot_mask
        if value == 0:
            assert kernel is None
            kernel = represented
    assert kernel == seed_mask and len(pivots) == SEED_BITS - 1
    value = product
    represented = 0
    for leading in sorted(pivots, reverse=True):
        if value & (1 << leading):
            pivot_value, pivot_mask = pivots[leading]
            value ^= pivot_value
            represented ^= pivot_mask
    if value:
        return None
    a, b = sorted((represented, represented ^ seed_mask))
    assert multiply(a << 1, b << 1) == product
    return a, b


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt = json.loads((HERE / "run_receipt.json").read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    assert receipt["status"] == "COMPLETE" and receipt["protocol_sha256"] == digest(HERE / "protocol.json")
    assert receipt["results_sha256"] == digest(HERE / "results.jsonl")
    assert protocol["source_sha256"]["panel"] == digest(HERE / "panel.json")
    assert protocol["source_sha256"]["support"] == digest(SUPPORT)
    rows = [json.loads(line) for line in (HERE / "results.jsonl").read_text().splitlines()]
    assert len(rows) == receipt["completed_executions"] == 200
    grouped = {}
    for row in rows:
        index = row["case_index"]
        assert row["name"] == panel["cases"][index]["name"]
        assert row["status"] == "COMPLETE" and row["returncode"] == 0
        assert row["stderr"] == "" and row["native_result"]["status"] == "COMPLETE"
        assert row["parent_wall_ns_exploratory"] < protocol["parent_cap_seconds"] * 1_000_000_000
        assert row["native_result"]["query_ns_exploratory"] < protocol["native_cap_seconds"] * 1_000_000_000
        assert row["native_result"]["peak_rss_bytes"] < protocol["rss_cap_bytes"]
        grouped.setdefault(index, {})[row["variant"]] = row
    support = {}
    for line in SUPPORT.read_text().splitlines():
        mask, column = map(int, line.split())
        support[mask] = column
    assert len(support) == 131307
    basis = [1 << (index + 1) for index in range(SEED_BITS)]
    half_basis = [halftrace(square(element)) for element in basis]
    trace_basis = [square(h) ^ h ^ square(element) for h, element in zip(half_basis, basis)]
    assert all(value == 0 for value in trace_basis)
    rank_counts = Counter()
    candidate_count = hit_count = positive_count = control_count = 0
    candidate_times = []
    baseline_times = []
    for index, case in enumerate(panel["cases"]):
        variants = grouped[index]
        assert set(variants) == ({"baseline", "candidate"} if index < 4 else {"candidate"})
        raw = variants["candidate"]["native_result"]
        coordinate = case["coordinate"]
        rotation = case["rotation"]
        unrotated = coordinate
        for _ in range(N - rotation if rotation else 0):
            unrotated = square(unrotated)
        rotated = unrotated
        for _ in range(rotation):
            rotated = square(rotated)
        assert rotated == coordinate
        if "unrotated_coordinate" in case:
            assert case["unrotated_coordinate"] == unrotated
        assert field_word(raw["supplied_reciprocal"]) == coordinate
        assert field_word(raw["unrotated_reciprocal"]) == unrotated
        c2 = square(unrotated)
        hc = halftrace(c2)
        trace = square(hc) ^ hc ^ c2
        assert trace in (0, 1) and raw["trace_bit"] == trace
        reciprocal = inverse(unrotated)
        constant = multiply(hc, reciprocal)
        columns = [multiply(h, reciprocal) for h in half_basis] + [reciprocal]
        rank, consistent, solutions = span_solutions(constant, columns, trace, trace_basis)
        assert raw["span_linear_rank"] == rank
        assert raw["span_consistent"] == consistent
        assert raw["span_candidates"] == len(solutions)
        rank_counts[rank] += 1
        candidate_count += len(solutions)
        expected_hits = []
        for solution in solutions:
            seed_mask = solution & ((1 << SEED_BITS) - 1)
            branch = (solution >> BRANCH_BIT) & 1
            if seed_mask == 0:
                continue
            product = constant
            for bit in range(SEED_BITS):
                if seed_mask & (1 << bit):
                    product ^= columns[bit]
            if branch:
                product ^= columns[BRANCH_BIT]
            assert product.bit_length() <= 37 and product & 3 == 0
            seed = seed_mask << 1
            assert multiply(1 ^ square(product), c2) ^ multiply(product, unrotated) ^ square(seed) == 0
            pair = recover_masks(seed_mask, product, basis)
            if pair is None:
                continue
            a, b = pair
            if a not in support or b not in support or support[a] == support[b]:
                continue
            expected_hits.append({"seed": seed_mask, "masks": [a, b],
                                  "columns": [support[a], support[b]],
                                  "product": product})
        actual_hits = [{"seed": hit["seed"], "masks": hit["masks"],
                        "columns": hit["columns"], "product": field_word(hit["product"])}
                       for hit in raw["hits"]]
        assert sorted(actual_hits, key=str) == sorted(expected_hits, key=str)
        hit_count += len(actual_hits)
        if case["expected_pair"] is None:
            assert actual_hits == []
            control_count += 1
        else:
            assert case["expected_pair"] in [hit["masks"] for hit in actual_hits]
            positive_count += 1
        if index < 4:
            old = variants["baseline"]["native_result"]
            for key in ("status", "supplied_reciprocal", "unrotated_reciprocal", "rotation",
                        "trace_bit", "linear_image_hits", "source_pair_hits", "column_rejects", "hits"):
                assert raw[key] == old[key]
            baseline_times.append(old["query_ns_exploratory"])
        candidate_times.append(raw["query_ns_exploratory"])
    result = {"status": "VERIFIED", "protocol_sha256": digest(HERE / "protocol.json"),
              "run_receipt_sha256": digest(HERE / "run_receipt.json"),
              "results_sha256": digest(HERE / "results.jsonl"),
              "verifier_source_sha256": digest(HERE / "verify.py"),
              "case_count": len(panel["cases"]), "positive_cases": positive_count,
              "zero_hit_controls": control_count, "linear_candidate_count": candidate_count,
              "accepted_hits": hit_count, "rank_counts": dict(sorted(rank_counts.items())),
              "candidate_query_ns_exploratory": {"min": min(candidate_times),
                  "median": statistics.median(candidate_times), "max": max(candidate_times)},
              "paired_baseline_query_ns_exploratory": baseline_times,
              "paired_candidate_query_ns_exploratory": candidate_times[:4]}
    (HERE / "verification.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "positive_cases": positive_count,
                      "zero_hit_controls": control_count, "rank_counts": result["rank_counts"]}))


if __name__ == "__main__":
    main()
