"""Exact quadratic evaluation rank on audited N41 suffix x and seed pairs."""

import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_seed_bin_quadratic_filter_20261009"
ORBITS = SOURCE / "x_orbits.bin"
PRODUCTION = SOURCE / "production.json"
BITS = 52  # x bits 1..40, left seed bits 0..5, right seed bits 0..5
FEATURES = 1 + BITS + BITS * (BITS - 1) // 2
ROWS = 1583568


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def record(data, index):
    raw = data[12 * index:12 * (index + 1)]
    if len(raw) != 12:
        raise ValueError("truncated orbit")
    left, right = raw[0], raw[1]
    x = int.from_bytes(raw[2:8], "little")
    pair_left = int.from_bytes(raw[8:10], "little")
    pair_right = int.from_bytes(raw[10:12], "little")
    if not (1 <= left <= 63 and 1 <= right <= 63 and x < 1 << 41 and
            x & 1 == 0 and pair_left < 1956 and pair_right < 1956):
        raise ValueError("invalid orbit")
    return left, right, x, pair_left, pair_right


def evaluation(left, right, x):
    value = (x >> 1) | (left << 40) | (right << 46)
    active = [bit for bit in range(BITS) if (value >> bit) & 1]
    row = 1
    for bit in active:
        row |= 1 << (1 + bit)
    for position, first in enumerate(active):
        for second in active[position + 1:]:
            feature = 1 + BITS + first * (2 * BITS - first - 1) // 2 + second - first - 1
            row |= 1 << feature
    return row


def freeze():
    production = json.loads(PRODUCTION.read_text())
    if production["status"] != "EXACT_X_ORBITS_WRITTEN" or production["counts"]["accepted_orbits"] != ROWS:
        raise ValueError("source census differs")
    new_json(HERE / "protocol.json", {
        "status": "FROZEN_BEFORE_RANK",
        "curve_id": "EC1N41Ckb1h7d5e80d3c4d0",
        "candidate_id": None,
        "input_law": "all exact sign-orbit x coordinates for the two W6 suffix pair domains at rotations 20 and 30, each with its generating six-bit seed sum",
        "feature_law": "all squarefree Boolean monomials of degree at most two in x bits 1..40, left seed bits 0..5, and right seed bits 0..5",
        "feature_count": FEATURES,
        "orbit_rows": ROWS,
        "shuffle_seed": 20261011,
        "max_rows_examined": 20000,
        "source_sha256": {"rank": sha(HERE / "rank.py"), "orbits": sha(ORBITS),
                          "production": sha(PRODUCTION)},
    })


def run():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["source_sha256"] == {
        "rank": sha(HERE / "rank.py"), "orbits": sha(ORBITS),
        "production": sha(PRODUCTION)}
    data = ORBITS.read_bytes()
    assert len(data) == ROWS * 12
    order = list(range(ROWS))
    random.Random(protocol["shuffle_seed"]).shuffle(order)
    pivots = {}
    witnesses = []
    start = time.perf_counter_ns()
    for attempted, index in enumerate(order[:protocol["max_rows_examined"]], 1):
        left, right, x, pair_left, pair_right = record(data, index)
        value = evaluation(left, right, x)
        while value:
            pivot = value.bit_length() - 1
            previous = pivots.get(pivot)
            if previous is None:
                pivots[pivot] = value
                witnesses.append({"source_index": index, "left_seed": left,
                                  "right_seed": right, "x": x,
                                  "left_pair_index": pair_left,
                                  "right_pair_index": pair_right})
                break
            value ^= previous
        if len(pivots) == FEATURES:
            break
    else:
        attempted = protocol["max_rows_examined"]
    result = {"status": "FULL_QUADRATIC_EVALUATION_RANK" if len(pivots) == FEATURES
              else "CENSORED_ROW_CAP", "feature_count": FEATURES,
              "rank": len(pivots), "rows_examined": attempted,
              "independent_witness_rows": len(witnesses),
              "protocol_sha256": sha(protocol_path),
              "orbit_sha256": sha(ORBITS),
              "rank_wall_ns_exploratory": time.perf_counter_ns() - start}
    new_json(HERE / "witnesses.json", witnesses)
    result["witnesses_sha256"] = sha(HERE / "witnesses.json")
    new_json(HERE / "result.json", result)
    print(result["status"], "rank", result["rank"], "rows", attempted)


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
