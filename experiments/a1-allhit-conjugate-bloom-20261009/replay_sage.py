"""Independently replay all recorded A1 all-hit incidences in checked Sage."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, matrix

HERE = Path(__file__).resolve().parent
DEGREE = 53
ORDER = 21_044_858_204_113
RECORD_BYTES = 12


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    export_path = HERE / "inputs/export.json"
    index_path = HERE / "inputs/index.bin"
    export = json.loads(export_path.read_text())
    raw_index = index_path.read_bytes()
    assert len(raw_index) == 735_000 * RECORD_BYTES
    K = GF(2**DEGREE, "a53")
    assert [i for i, c in enumerate(K.modulus().list()) if c] == [0, 1, 2, 6, 53]
    E = EllipticCurve(K, [1, 0, 0, 0, 1])
    powers = [K.gen()**i for i in range(DEGREE)]
    field_cache = {}

    def field(value):
        if value not in field_cache:
            field_cache[value] = sum((powers[i] for i in range(DEGREE)
                                      if value >> i & 1), K(0))
        return field_cache[value]

    point_cache = {}

    def point(coords):
        key = tuple(coords) if coords is not None else None
        if key not in point_cache:
            point_cache[key] = E(0) if key is None else E(field(key[0]), field(key[1]))
        return point_cache[key]

    def bits(value):
        return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))

    def frobenius(P):
        return P if P.is_zero() else E(P[0]**2, P[1]**2)

    def exact_record(key):
        low, high = 0, 735_000
        while low < high:
            mid = (low + high) // 2
            offset = mid * RECORD_BYTES
            middle_key = int.from_bytes(raw_index[offset:offset + 8], "little")
            if middle_key < key:
                low = mid + 1
            else:
                high = mid
        assert low < 735_000
        offset = low * RECORD_BYTES
        assert int.from_bytes(raw_index[offset:offset + 8], "little") == key
        return [raw_index[offset + 8], raw_index[offset + 9],
                raw_index[offset + 10], 1 if raw_index[offset + 11] else -1]

    seeds = [point(coords) for coords in export["seed_points"]]
    reps = [point(entry["point"]) for entry in export["representatives"]]
    base = export["ordered_base"]
    logs = [int(value) for value in export["seed_logs"]]
    assert logs[0] == 1 and all(logs[i] * seeds[0] == seeds[i] for i in range(6))
    per_stream = {}
    for stream in ("primary", "disjoint"):
        workload_path = HERE / f"inputs/{stream}.json"
        receipt_path = HERE / f"results/{stream}_on.json"
        workload = json.loads(workload_path.read_text())
        result = json.loads(receipt_path.read_text())["raw_result"]
        assert result["status"] == "verified" and result["final_rank"] == 5
        rows = []
        incidences = 0
        for event in result["relation_events"]:
            query_record = workload["queries"][event["query_index"] - 1]
            scalar = int(query_record["known_scalar"])
            assert scalar == event["known_scalar"]
            Q = scalar * seeds[0]
            seen = set()
            for incidence in event["incidences"]:
                pair = incidence["pair_record"]
                third = point(base[incidence["third_base_index"]]["point"])
                difference = Q - third
                assert not difference.is_zero()
                x = difference[0]
                key = bits(x)
                for _ in range(1, DEGREE):
                    x = x**2
                    key = min(key, bits(x))
                assert exact_record(key) == pair
                left, right, relative, side = pair
                second = reps[right]
                for _ in range(relative):
                    second = frobenius(second)
                if side == -1:
                    second = -second
                pair_sum = reps[left] + second
                for _ in range(incidence["global_shift"]):
                    pair_sum = frobenius(pair_sum)
                if incidence["global_sign"] == -1:
                    pair_sum = -pair_sum
                assert pair_sum == difference and difference + third == Q
                row = [int(value) for value in incidence["row"]]
                assert sum((row[i] * seeds[i] for i in range(6)), E(0)) == Q
                assert sum(row[i] * logs[i] for i in range(6)) % ORDER == scalar
                seen.add(tuple(row))
                incidences += 1
            assert set(map(tuple, event["rows"])) == seen
            rows.extend([row[1:] for row in event["rows"]])
            assert matrix(GF(ORDER), rows).rank() == event["matrix_rank"]
        assert incidences == result["raw_hit_incidences"]
        assert matrix(GF(ORDER), rows).rank() == 5
        per_stream[stream] = {"status": "verified", "queries": result["query_count"],
                              "ordered_incidences_verified": incidences,
                              "weighted_rows_verified": len(rows), "rank": 5,
                              "workload_sha256": digest(workload_path),
                              "candidate_receipt_sha256": digest(receipt_path)}
    output = {"status": "verified", "degree": DEGREE, "subgroup_order": ORDER,
              "filter_index_sha256": digest(index_path),
              "export_sha256": digest(export_path), "per_stream": per_stream,
              "checked_sage_runtime_sha256": digest(HERE / "results/sage_runtime.json"),
              "checker_sha256": digest(Path(__file__))}
    with (HERE / "results/sage_replay.json").open("x") as file:
        json.dump(output, file, sort_keys=True, indent=2)
        file.write("\n")
    print(json.dumps({"status": "verified", "streams": per_stream}))


if __name__ == "__main__":
    main()
