#!/usr/bin/env python3
"""Run the frozen normal-basis barrel control panel without Sage."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from normal_barrel import NormalBasis, barrel, square

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/ecc2k130-orbit-closed-w24-seed-20261006"
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def column_digest(columns: tuple[int, ...]) -> str:
    payload = json.dumps([str(value) for value in columns], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    config = json.loads(CONFIG.read_text())
    assert config["field_degree"] == 131
    assert config["barrel_layers"] == [1, 2, 4, 8, 16, 32, 64, 128]
    assert sha256(PARENT / "runs/R1/result.json") == config["parent_result_sha256"]
    assert sha256(PARENT / "orbit_seed.py") == config["parent_orbit_seed_sha256"]
    parent = json.loads((PARENT / "runs/R1/result.json").read_text())
    assert len(parent["positive"]) == 56 and len(parent["negative"]) == 64

    started = time.monotonic()
    normal = NormalBasis.first(config["normal_element_domain"],
                               config["normal_element_search_max_counter"])
    controls = []
    for kind in ("positive", "negative"):
        for index, row in enumerate(parent[kind]):
            word = int(row["orbit_x"] if kind == "positive" else row["x"])
            code = normal.to_normal(word)
            if normal.to_polynomial(code) != word:
                raise ArithmeticError("normal conversion failed round trip")
            powers = [word]
            for _ in range(1, 131):
                powers.append(square(powers[-1]))
            tested = []
            for exponent in config["control_exponents"]:
                rotated = barrel(code, exponent)
                output = normal.to_polynomial(rotated)
                if output != powers[exponent]:
                    raise ArithmeticError("barrel differs from polynomial Frobenius")
                tested.append({"exponent": exponent, "normal_code": str(rotated),
                               "polynomial_word": str(output)})
            control = {"kind": kind, "index": index, "input_word": str(word),
                       "normal_code": str(code), "rotations": tested}
            if kind == "positive":
                seed_code = normal.seed_code(row["mask"])
                planted_output = normal.to_polynomial(barrel(seed_code, row["planted_exponent"]))
                if planted_output != word:
                    raise ArithmeticError("planted seed/exponent did not match parent")
                control["mask"] = row["mask"]
                control["planted_exponent"] = row["planted_exponent"]
                control["seed_normal_code"] = str(seed_code)
            controls.append(control)
            if time.monotonic() - started > config["producer_limit_seconds"]:
                raise TimeoutError("frozen producer wall limit")
    for invalid in (131, 255):
        try:
            barrel(0, invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-range exponent accepted")
    gate_counts = normal.gate_counts()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if peak > config["peak_rss_limit_bytes"]:
        raise MemoryError("frozen producer RSS cap")
    result = {
        "schema": "ecc2k130-w24-normal-barrel-result-v1",
        "candidate_id": None,
        "config_sha256": sha256(CONFIG),
        "parent_result_sha256": sha256(PARENT / "runs/R1/result.json"),
        "source_sha256": {"normal_barrel.py": sha256(HERE / "normal_barrel.py"),
                          "run.py": sha256(HERE / "run.py")},
        "field_element_encoding": "decimal_string_little_endian_polynomial_basis_integer",
        "normal_element": str(normal.element),
        "normal_element_search_counter": normal.search_counter,
        "normal_orbit_polynomial_words": [str(value) for value in normal.orbit],
        "w24_to_normal_columns": [str(value) for value in normal.w24_to_normal_columns],
        "normal_to_polynomial_columns": [str(value) for value in normal.orbit],
        "conversion_matrix_sha256": {
            "w24_to_normal": column_digest(normal.w24_to_normal_columns),
            "normal_to_polynomial": column_digest(normal.orbit),
        },
        "gate_counts": gate_counts,
        "control_exponents": config["control_exponents"],
        "controls": controls,
        "counts": {"positive_inputs": 56, "negative_inputs": 64,
                   "round_trips": len(controls),
                   "frozen_rotations": len(controls) * len(config["control_exponents"]),
                   "planted_parent_matches": 56,
                   "invalid_exponents_rejected": 2},
        "producer_wall_ms_exploratory": (time.monotonic() - started) * 1000,
        "producer_peak_rss_bytes": peak,
        "ordinary_pdp_queries": 0,
        "natural_pdp_yield": None,
        "verified_novel_rank": None,
        "target_online_ms": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
