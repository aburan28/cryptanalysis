#!/usr/bin/env python3
"""Mixed cubic rank gate for two still-free N41 pair domains.

The feature family is fixed in protocol.json before this program runs.  A
full relative rank proves that no equation in that family can connect the
two pair seed sums to the x-coordinate of their group sum.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
SOURCE = GOAL / "n41_two_pair_mask_decoder_rank_20261008"
sys.path.insert(0, str(SOURCE.parent / "n41_two_free_pair_occupancy_20261009"))
from arithmetic_snapshot import Curve, Field  # noqa: E402

PROTOCOL = HERE / "protocol.json"
RESULT = HERE / "result.json"
FIELD_BITS = 41
SEED_BITS = 12
X_BITS = 40
VARIABLES = SEED_BITS + X_BITS


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def feature_family() -> tuple[list[tuple[int, ...]], dict[tuple[int, ...], int]]:
    terms: list[tuple[int, ...]] = [()]
    for degree in (1, 2):
        terms.extend(itertools.combinations(range(VARIABLES), degree))
    terms.extend(term for term in itertools.combinations(range(VARIABLES), 3)
                 if term[0] < SEED_BITS)
    return terms, {term: index for index, term in enumerate(terms)}


def row_bits(seed_left: int, seed_right: int, x: int,
             term_index: dict[tuple[int, ...], int]) -> int:
    if x & 1 or seed_left >= 1 << 6 or seed_right >= 1 << 6:
        raise ValueError("row is outside the frozen subgroup x/seed encoding")
    packed = seed_left | (seed_right << 6) | ((x >> 1) << 12)
    active = [index for index in range(VARIABLES) if packed >> index & 1]
    value = 1
    for degree in (1, 2, 3):
        for term in itertools.combinations(active, degree):
            if degree == 3 and term[0] >= SEED_BITS:
                continue
            value |= 1 << term_index[term]
    return value


def coordinate_bits(x: int) -> int:
    active = [bit for bit in range(X_BITS) if (x >> (bit + 1)) & 1]
    value = 1
    for bit in active:
        value |= 1 << (1 + bit)
    for at, bit in enumerate(active):
        base = 1 + X_BITS + bit * (2 * X_BITS - bit - 1) // 2
        for other in active[at + 1:]:
            value |= 1 << (base + other - bit - 1)
    return value


def insert_high(basis: dict[int, int], value: int) -> bool:
    while value:
        pivot = value.bit_length() - 1
        previous = basis.get(pivot)
        if previous is None:
            basis[pivot] = value
            return True
        value ^= previous
    return False


def parity(value: int) -> int:
    return value.bit_count() & 1


def find_mixed_equation(basis: dict[int, int], terms: list[tuple[int, ...]],
                        sample_vectors: list[int]) -> tuple[list[int], int] | None:
    free = [index for index in range(len(terms)) if index not in basis]
    for index in free:
        equation = 1 << index
        for pivot in sorted(basis):
            if parity(basis[pivot] & equation):
                equation |= 1 << pivot
        support = [index for index in range(len(terms)) if equation >> index & 1]
        if not any(term and term[0] < SEED_BITS for term in
                   (terms[index] for index in support)):
            continue
        if any(parity(vector & equation) for vector in sample_vectors):
            raise ValueError("extracted equation fails a frozen exact row")
        return support, equation
    return None


def pair_states(curve: Curve, source: list) -> list[tuple[int, tuple[int, int]]]:
    states = []
    for left in range(len(source)):
        for right in range(left + 1, len(source)):
            if source[left][2] == source[right][2]:
                continue
            point = curve.add(tuple(source[left][:2]), tuple(source[right][:2]))
            if point is None:
                raise ValueError("admissible pair unexpectedly sums to identity")
            states.append((source[left][3] ^ source[right][3], point))
    if len(states) != 1956:
        raise ValueError("frozen pair-state count changed")
    return states


def main() -> None:
    if RESULT.exists():
        raise FileExistsError("preserve the first frozen rank result")
    protocol = json.loads(PROTOCOL.read_text())
    paths = {key: Path(value) for key, value in protocol["inputs"].items()}
    if sha(Path(__file__)) != protocol["screen_sha256"]:
        raise ValueError("rank-screen source changed after freeze")
    for name, path in paths.items():
        if sha(path) != protocol["input_sha256"][name]:
            raise ValueError(f"frozen input changed: {name}")
    terms, term_index = feature_family()
    if len(terms) != protocol["feature_count"]:
        raise ValueError("feature family changed")
    decoded = json.loads(paths["decoded_rows"].read_text())
    holdout = json.loads(paths["holdout_rows"].read_text())
    geometry = json.loads(paths["geometry"].read_text())["n41"]
    if (decoded["curve_id"] != holdout["curve_id"] or
            decoded["curve_id"] != geometry["curve_id"] or
            len(decoded["rows"]) != 8192 or len(holdout["rows"]) != 8192):
        raise ValueError("frozen exact-row inventory changed")
    field = Field(FIELD_BITS, [0, 3])
    curve = Curve(field, 0)
    domains = [pair_states(curve, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in protocol["pair_rotations"]]
    start_ns = time.monotonic_ns()
    deadline_ns = start_ns + int(protocol["limits"]["wall_seconds"] * 1e9)
    basis: dict[int, int] = {}
    coordinate_basis: dict[int, int] = {}
    pivots = []
    vectors: list[int] = []
    checked = 0
    status = "SAMPLE_EXHAUSTED"
    try:
        for source_name, source_rows in (("decoded", decoded["rows"]),
                                         ("holdout", holdout["rows"])):
            for index, record in enumerate(source_rows):
                left_index, right_index = record["pair_state_indices"][-2:]
                left, right = domains[0][left_index], domains[1][right_index]
                seed_left, seed_right = left[0], right[0]
                if source_name == "decoded" and record["pair_seed_sums"] != [seed_left, seed_right]:
                    raise ValueError("source seed-sum decoder changed")
                point = curve.add(left[1], right[1])
                if point is None or list(point) != record["sum_point"]:
                    raise ValueError("saved exact group sum changed")
                vector = row_bits(seed_left, seed_right, point[0], term_index)
                vectors.append(vector)
                insert_high(coordinate_basis, coordinate_bits(point[0]))
                if insert_high(basis, vector):
                    pivots.append(checked)
                checked += 1
                if len(basis) == len(terms):
                    status = "FULL_MIXED_CUBIC_RANK"
                    break
                if checked % 64 == 0:
                    if time.monotonic_ns() >= deadline_ns:
                        status = "TIME_CAP"
                        break
                    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    if sys.platform != "darwin":
                        rss *= 1024
                    if rss >= protocol["limits"]["rss_bytes"]:
                        status = "MEMORY_CAP"
                        break
            if status != "SAMPLE_EXHAUSTED":
                break
    except Exception as exc:
        status = "PRODUCER_FAILURE"
        error = {"type": type(exc).__name__, "message": str(exc)}
    else:
        error = None
    coordinate_feature_count = 1 + X_BITS + X_BITS * (X_BITS - 1) // 2
    full_nullity = len(terms) - len(basis)
    coordinate_nullity = coordinate_feature_count - len(coordinate_basis)
    mixed_excess_nullity = full_nullity - coordinate_nullity
    candidate = None
    if status == "SAMPLE_EXHAUSTED" and mixed_excess_nullity > 0:
        selected = find_mixed_equation(basis, terms, vectors)
        if selected is not None:
            support, equation = selected
            candidate = {"term_indices": support, "term_count": len(support),
                         "support_sha256": hashlib.sha256(
                             ",".join(map(str, support)).encode()).hexdigest(),
                         "sample_violations": sum(parity(vector & equation) for vector in vectors)}
    elapsed_ns = time.monotonic_ns() - start_ns
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    result = {
        "kind": protocol["kind"], "status": status, "error": error,
        "proposal_id": protocol["proposal_id"], "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "target_count": 1,
        "public_target_q": protocol["public_target_q"],
        "feature_count": len(terms), "coordinate_feature_count": coordinate_feature_count,
        "exact_pair_rows_checked": checked, "pair_domain_sizes": [len(x) for x in domains],
        "rank": len(basis), "coordinate_rank": len(coordinate_basis),
        "mixed_excess_nullity": mixed_excess_nullity,
        "pivotal_row_indices_sha256": hashlib.sha256(
            ",".join(map(str, pivots)).encode()).hexdigest(),
        "candidate_equation": candidate,
        "exploratory_wall_ns": elapsed_ns, "peak_rss_bytes": rss,
        "source_sha256": {"protocol": sha(PROTOCOL), "screen": sha(Path(__file__)),
                          **{key: sha(path) for key, path in paths.items()}},
        "claim_boundary": protocol["claim_boundary"],
    }
    with RESULT.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": status, "rank": len(basis),
                      "coordinate_rank": len(coordinate_basis),
                      "rows": checked, "wall_s": elapsed_ns / 1e9}, sort_keys=True))


if __name__ == "__main__":
    main()
