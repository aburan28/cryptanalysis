#!/usr/bin/env sage -python
"""Independent Sage replay of the frozen normal-basis barrel panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import GF, PolynomialRing, matrix, vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"
DEGREE = 131
MASK = (1 << DEGREE) - 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def column_digest(columns) -> str:
    payload = json.dumps([str(value) for value in columns], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def bits(word: int):
    return [(word >> bit) & 1 for bit in range(DEGREE)]


def integer(coords) -> int:
    return sum(int(value) << bit for bit, value in enumerate(coords))


def xor_count(columns) -> int:
    return sum(max(0, sum((column >> bit) & 1 for column in columns) - 1)
               for bit in range(DEGREE))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    check(not args.out.exists(), "refusing to overwrite verifier output")
    config = json.loads(CONFIG.read_text())
    result = json.loads(args.result.read_text())
    runtime = json.loads(args.runtime_info.read_text())
    check(runtime["status"] == "verified", "checked Sage runtime missing")
    check(result["config_sha256"] == digest(CONFIG), "protocol hash mismatch")
    check(result["candidate_id"] is None, "candidate must remain a proposal")
    check(result["natural_pdp_yield"] is None and result["target_online_ms"] is None,
          "unmeasured PDP/target metric was populated")
    for name, expected in result["source_sha256"].items():
        check(digest(HERE / name) == expected, f"source changed: {name}")
    parent_path = ROOT / "experiments/ecc2k130-orbit-closed-w24-seed-20261006/runs/R1/result.json"
    check(digest(parent_path) == config["parent_result_sha256"], "parent result changed")
    check(result["parent_result_sha256"] == digest(parent_path), "wrong parent result")
    parent = json.loads(parent_path.read_text())

    started = time.monotonic()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**DEGREE, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(word):
        word = int(word)
        check(0 <= word <= MASK, "noncanonical field word")
        return field(sum(t**bit for bit in range(DEGREE) if (word >> bit) & 1))

    def encode(value):
        return sum(int(bit) << index
                   for index, bit in enumerate(value.polynomial().list()))

    domain = config["normal_element_domain"]
    element = None
    orbit = None
    counter = None
    for candidate_counter in range(config["normal_element_search_max_counter"] + 1):
        raw = hashlib.sha256(f"{domain}|{candidate_counter}".encode()).digest()[:17]
        proposed = int.from_bytes(raw, "big") & MASK
        if proposed == 0:
            continue
        power = decode(proposed)
        proposed_orbit = [power]
        for _ in range(1, DEGREE):
            proposed_orbit.append(proposed_orbit[-1]**2)
        rows = [[int((encode(value) >> bit) & 1) for value in proposed_orbit]
                for bit in range(DEGREE)]
        candidate_matrix = matrix(GF(2), rows)
        if candidate_matrix.rank() == DEGREE:
            counter, element, orbit = candidate_counter, proposed, proposed_orbit
            break
    check(element is not None, "no normal element found")
    check(counter == result["normal_element_search_counter"], "normal search counter mismatch")
    check(str(element) == result["normal_element"], "normal element mismatch")
    check([str(encode(value)) for value in orbit] == result["normal_orbit_polynomial_words"],
          "normal orbit mismatch")
    check(result["normal_to_polynomial_columns"] == result["normal_orbit_polynomial_words"],
          "output-map columns mismatch")
    inverse = candidate_matrix.inverse()

    def normal_code(value):
        return integer(inverse * vector(GF(2), bits(encode(value))))

    polynomial_columns = [normal_code(decode(1 << bit)) for bit in range(DEGREE)]
    check([str(value) for value in polynomial_columns] ==
          result["polynomial_to_normal_columns"],
          "full polynomial-to-normal columns mismatch")
    w24 = [field.gen()**j + (field.gen()**j).trace() for j in range(1, 25)]
    seed_columns = [normal_code(value) for value in w24]
    check([str(value) for value in seed_columns] == result["w24_to_normal_columns"],
          "W24 input-map columns mismatch")
    check(result["conversion_matrix_sha256"] == {
        "polynomial_to_normal": column_digest(polynomial_columns),
        "w24_to_normal": column_digest(seed_columns),
        "normal_to_polynomial": column_digest([encode(value) for value in orbit]),
    }, "conversion matrix digest mismatch")
    muxes = DEGREE * len(config["barrel_layers"])
    input_xors = xor_count(seed_columns)
    output_xors = xor_count([encode(value) for value in orbit])
    expected_gates = {
        "per_leaf_seed_map_xor": input_xors,
        "per_leaf_barrel_mux": muxes,
        "per_leaf_barrel_and_equivalent": muxes,
        "per_leaf_barrel_xor_equivalent": 2 * muxes,
        "per_leaf_output_map_xor": output_xors,
        "five_leaf_seed_map_xor": 5 * input_xors,
        "five_leaf_barrel_mux": 5 * muxes,
        "five_leaf_barrel_and_equivalent": 5 * muxes,
        "five_leaf_barrel_xor_equivalent": 10 * muxes,
        "five_leaf_output_map_xor": 5 * output_xors,
    }
    check(result["gate_counts"] == expected_gates, "circuit gate ledger mismatch")
    check(result["control_exponents"] == config["control_exponents"],
          "control exponents changed")

    controls = result["controls"]
    check(len(controls) == 120, "expected 120 frozen controls")
    for position, row in enumerate(controls):
        kind = "positive" if position < 56 else "negative"
        index = position if kind == "positive" else position - 56
        parent_row = parent[kind][index]
        word = parent_row["orbit_x"] if kind == "positive" else parent_row["x"]
        check(row["kind"] == kind and row["index"] == index, "control order mismatch")
        check(row["input_word"] == word, "parent field input mismatch")
        value = decode(word)
        code = normal_code(value)
        check(row["normal_code"] == str(code), "normal conversion mismatch")
        check(sum(orbit[bit] for bit in range(DEGREE) if (code >> bit) & 1) == value,
              "normal round trip mismatch")
        check(len(row["rotations"]) == len(config["control_exponents"]),
              "missing frozen rotation")
        for exponent, observed in zip(config["control_exponents"], row["rotations"]):
            check(observed["exponent"] == exponent, "rotation exponent mismatch")
            expected_code = sum(((code >> bit) & 1) << ((bit + exponent) % DEGREE)
                                for bit in range(DEGREE))
            check(observed["normal_code"] == str(expected_code), "barrel rotation mismatch")
            check(observed["polynomial_word"] == str(encode(value**(1 << exponent))),
                  "field Frobenius mismatch")
            check(normal_code(value**(1 << exponent)) == expected_code,
                  "normal Frobenius mismatch")
        if kind == "positive":
            mask = parent_row["mask"]
            exponent = parent_row["planted_exponent"]
            check(row["mask"] == mask and row["planted_exponent"] == exponent,
                  "parent planted witness mismatch")
            seed = sum(w24[bit] for bit in range(24) if (mask >> bit) & 1)
            seed_code = 0
            for bit in range(24):
                if (mask >> bit) & 1:
                    seed_code ^= seed_columns[bit]
            check(row["seed_normal_code"] == str(seed_code), "W24 seed-map mismatch")
            check(seed**(1 << exponent) == value, "planted parent Frobenius mismatch")
        if time.monotonic() - started > config["sage_verifier_limit_seconds"]:
            raise TimeoutError("frozen independent Sage wall limit")

    check(result["counts"] == {
        "positive_inputs": 56, "negative_inputs": 64, "round_trips": 120,
        "frozen_rotations": 120 * len(config["control_exponents"]),
        "planted_parent_matches": 56, "invalid_exponents_rejected": 2,
    }, "control counts mismatch")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    check(peak <= config["peak_rss_limit_bytes"], "independent Sage RSS cap")
    report = {
        "status": "PASS_INDEPENDENT_SAGE_NORMAL_BASIS_REPLAY",
        "result_sha256": digest(args.result),
        "config_sha256": digest(CONFIG),
        "verifier_source_sha256": digest(Path(__file__)),
        "sage_runtime_info_sha256": digest(args.runtime_info),
        "normal_element_search_counter": counter,
        "normal_basis_rank": candidate_matrix.rank(),
        "round_trips": len(controls),
        "frobenius_rotations": len(controls) * len(config["control_exponents"]),
        "planted_parent_matches": 56,
        "gate_counts": expected_gates,
        "verifier_wall_ms_exploratory": (time.monotonic() - started) * 1000,
        "verifier_peak_rss_bytes": peak,
        "candidate_id": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
