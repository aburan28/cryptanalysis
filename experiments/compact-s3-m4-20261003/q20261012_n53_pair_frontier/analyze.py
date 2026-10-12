#!/usr/bin/env python3
"""Q1511: exact table/query-prefix rank frontier from frozen Q1457 witnesses."""
from __future__ import annotations

import base64
import bisect
import gzip
import hashlib
import json
import math
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
SOURCE = PARENT / "q20261011_n53_full_pipeline"
PAIR = PARENT / "q20261011_n53_native_pair"
QUERY_FILE = Path("/private/tmp/q1457_n53_setup/queries.bin")
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
import curves  # noqa: E402
import field  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Ranker:
    def __init__(self, modulus: int):
        self.modulus = modulus
        self.pivots: dict[int, dict[int, int]] = {}

    def insert(self, original: dict[int, int]) -> int:
        modulus = self.modulus
        pivots = self.pivots
        row = dict(original)
        while row:
            col = min(row)
            if col not in pivots:
                inv = pow(row[col], -1, modulus)
                pivots[col] = {k: v * inv % modulus for k, v in row.items()}
                break
            factor = row[col]
            for k, v in pivots[col].items():
                value = (row.get(k, 0) - factor * v) % modulus
                if value:
                    row[k] = value
                else:
                    row.pop(k, None)
        return len(pivots)


def sparse_rank(rows: list[dict[int, int]], modulus: int, goal: int) -> int:
    ranker = Ranker(modulus)
    for row in rows:
        if ranker.insert(row) == goal:
            break
    return len(ranker.pivots)


def main() -> None:
    protocol = json.loads((SOURCE / "protocol.json").read_text())
    freeze = json.loads((SOURCE / "freeze.json").read_text())
    measurement = json.loads((SOURCE / "native_measurement.json").read_text())
    replay = json.loads((SOURCE / "independent_replay.json").read_text())
    assert replay["status"] == "PASS"
    assert replay["measurement_sha256"] == digest(SOURCE / "native_measurement.json")
    assert measurement["freeze_sha256"] == digest(SOURCE / "freeze.json")
    assert measurement["factor_base_enumerated_set_sha256"] == protocol["factor_base_enumerated_set_sha256"]
    assert measurement["status"] == "completed_query_cap"
    if QUERY_FILE.exists():
        assert digest(QUERY_FILE) == freeze["query_file_sha256"]
    assert digest(PAIR / "inputs/base.bin") == freeze["base_input_sha256"]
    assert len(measurement["matches"]) == len(replay["relations"]) == 400

    onb = field.Onb(53)
    curve = curves.Curve(onb)
    quotient = OrbitKey(onb)
    with gzip.open(PARENT / "bases/n53_weight3_orbits.json.gz", "rt") as stream:
        base_archive = json.load(stream)["factor_base"]
    packed = base64.b64decode(base_archive["packed_canonical_x_keys_base64"])
    assert hashlib.sha256(packed).hexdigest() == protocol["factor_base_enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i + 7], "little") for i in range(0, len(packed), 7)]
    K = protocol["factor_base_folded_columns_K"]
    r = protocol["subgroup_order"]
    eigen = protocol["frobenius_eigenvalue_mod_r"]
    assert len(keys) == K == replay["matrix_rank"]
    representatives = [curve.pointFromX(onb.fromCoords(x)) for x in keys]
    canonical = {}
    for column, point in enumerate(representatives):
        assert point is not None
        key, exponent, sign = quotient.canonical(point)
        assert key not in canonical
        canonical[key] = (column, exponent, sign, point)

    records = []
    for match, witness in zip(measurement["matches"], replay["relations"]):
        query, ordinal = match[:2]
        assert witness["query_number"] == query
        assert witness["table_state_ordinal"] == ordinal
        row: dict[int, int] = {}
        for coords in witness["points"]:
            point = tuple(coords)
            key, exponent, sign = quotient.canonical(point)
            column, rep_exp, rep_sign, representative = canonical[key]
            shift = (rep_exp - exponent) % 53
            transformed = curve.frob(representative, shift)
            if sign * rep_sign == -1:
                transformed = curve.neg(transformed)
            assert transformed == point
            coeff = sign * rep_sign * pow(eigen, shift, r) % r
            row[column] = (row.get(column, 0) + coeff) % r
            if row[column] == 0:
                del row[column]
        assert sum(replay["factor_base_logs"][col] * coeff for col, coeff in row.items()) % r == 1
        records.append({"query": query, "ordinal": ordinal, "row": row})
    assert sparse_rank([x["row"] for x in records], r, K) == K

    # Scan the frozen query stream once to charge identity skips at each
    # possible stopping prefix. All other queries take two pair additions.
    raw_base = (PAIR / "inputs/base.bin").read_bytes()
    points = [(int.from_bytes(raw_base[i:i + 16], "little"),
               int.from_bytes(raw_base[i + 16:i + 32], "little"))
              for i in range(0, len(raw_base), 32)]
    assert len(points) == protocol["factor_base_actual_B"]
    indices = {point: i for i, point in enumerate(points)}
    negatives = [indices.get((x, x ^ y), -1) for x, y in points]
    identity_positions = []
    if QUERY_FILE.exists():
        with QUERY_FILE.open("rb") as stream:
            position = 0
            while block := stream.read(4 * 262144):
                assert len(block) % 4 == 0
                for first, second in struct.iter_unpack("<HH", block):
                    position += 1
                    if negatives[first] == second:
                        identity_positions.append(position)
    else:
        rng = random.Random(freeze["query_seed"])
        query_hash = hashlib.sha256()
        for position in range(1, freeze["query_count"] + 1):
            first = rng.randrange(len(points))
            second = rng.randrange(len(points))
            query_hash.update(struct.pack("<HH", first, second))
            if negatives[first] == second:
                identity_positions.append(position)
        assert query_hash.hexdigest() == freeze["query_file_sha256"]
    assert position == measurement["query_samples_processed"]
    assert len(identity_positions) == measurement["query_skipped_identity_pairs"]

    ordered_by_ordinal = sorted(records, key=lambda x: x["ordinal"])
    table_min = None
    ordinal_ranker = Ranker(r)
    for i, record in enumerate(ordered_by_ordinal):
        rank = ordinal_ranker.insert(record["row"])
        if i + 1 < len(ordered_by_ordinal) and ordered_by_ordinal[i + 1]["ordinal"] == record["ordinal"]:
            continue
        if rank == K:
            table_min = record["ordinal"]
            break
    assert table_min is not None

    candidates = []
    for table_cap in sorted({x["ordinal"] for x in records if x["ordinal"] >= table_min}):
        chosen = [x for x in records if x["ordinal"] <= table_cap]
        query_ranker = Ranker(r)
        for i, record in enumerate(chosen):
            if query_ranker.insert(record["row"]) == K:
                query_cap = record["query"]
                break
        else:
            raise AssertionError("table prefix lost rank")
        skipped = bisect.bisect_right(identity_positions, query_cap)
        cost = table_cap + 2 * query_cap - skipped
        candidates.append({"table_states": table_cap, "query_representatives": query_cap,
                           "identity_queries": skipped, "charged_pair_add_attempts": cost,
                           "verified_relations_at_stop": i + 1})
    optimum = min(candidates, key=lambda x: (x["charged_pair_add_attempts"], x["table_states"]))
    full_cost = measurement["charged_pair_add_attempts"]
    assert candidates[-1]["table_states"] <= measurement["table_states_generated"]
    assert optimum["charged_pair_add_attempts"] <= full_cost

    grid = []
    for cap in [500000, 1000000, 1500000, 2000000, 2250000, 2500000, 2600000, 2700000, measurement["table_states_generated"]]:
        selected = [x for x in records if x["ordinal"] <= cap]
        grid.append({"table_states": cap, "verified_relations_at_30m_queries": len(selected),
                     "rank_at_30m_queries": sparse_rank([x["row"] for x in selected], r, K)})
    result = {
        "proposal_id": "Q1511", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": K,
        "factor_base_enumerated_set_sha256": protocol["factor_base_enumerated_set_sha256"],
        "method": "PDP4mitm/RCenum frozen-prefix counterfactual with exact modular rank",
        "source_sha256": digest(Path(__file__)),
        "input_sha256": {name: digest(SOURCE / name) for name in
                         ("protocol.json", "freeze.json", "native_measurement.json", "independent_replay.json")},
        "base_archive_sha256": digest(PARENT / "bases/n53_weight3_orbits.json.gz"),
        "base_points_sha256": digest(PAIR / "inputs/base.bin"),
        "query_file_sha256": freeze["query_file_sha256"],
        "full_run": {"table_states": measurement["table_states_generated"],
                     "query_representatives": measurement["query_samples_processed"],
                     "charged_pair_add_attempts": full_cost,
                     "operation_log2": math.log2(full_cost)},
        "smallest_full_rank_table_states": table_min,
        "best_frozen_prefix": {**optimum,
                               "operation_log2": math.log2(optimum["charged_pair_add_attempts"]),
                               "saved_pair_add_attempts": full_cost - optimum["charged_pair_add_attempts"],
                               "saved_work_bits": math.log2(full_cost / optimum["charged_pair_add_attempts"])},
        "rank_grid": grid,
        "feasible_prefix_count": len(candidates),
        "prefix_frontier": candidates,
        "complete_n131_solve_operation_log2": None,
    }
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("Q1511", K, "table minimum", table_min, "best", optimum,
          "savings bits", result["best_frozen_prefix"]["saved_work_bits"])


if __name__ == "__main__":
    main()
