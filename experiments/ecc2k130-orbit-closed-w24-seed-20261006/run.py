#!/usr/bin/env python3
"""Run the frozen seed-plus-Frobenius membership controls without Sage."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from orbit_seed import DEGREE, FIELD_MASK, OrbitClosedW24, frobenius, seed_from_mask

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode_pair(pair: list[int]) -> list[str]:
    return [str(value) for value in pair]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    config = json.loads(CONFIG.read_text())
    assert config["field_modulus_exponents"] == [131, 13, 2, 1, 0]
    assert config["w_dimension"] == 24
    assert config["source_curve_id"] == "EC1N131Ckb1h136f03e58c98"
    source_path = ROOT / config["source_controls_path"]
    assert sha256(source_path) == config["source_controls_sha256"]
    source = json.loads(source_path.read_text())
    assert source["source_curve_id"] == config["source_curve_id"]
    started = time.monotonic()
    oracle = OrbitClosedW24()
    controls = [source["source"][i] for i in config["source_controls_indices"]]
    exponents = config["frobenius_exponents"]
    positive = []
    group = []
    for index, control in enumerate(controls):
        mask = control["mask"]
        seed = seed_from_mask(mask, oracle.basis)
        for exponent in exponents:
            orbit_x = frobenius(seed, exponent)
            witnesses, reductions = oracle.witnesses(orbit_x)
            if {"exponent": exponent, "mask": mask} not in witnesses:
                raise ArithmeticError("planted field witness not returned")
            positive.append({
                "control_index": config["source_controls_indices"][index],
                "mask": mask,
                "planted_exponent": exponent,
                "orbit_x": str(orbit_x),
                "witnesses": witnesses,
                "span_tests": DEGREE,
                "xor_reductions": reductions,
            })
        group_exponent = exponents[index % len(exponents)]
        q = control["source"]
        group.append({
            "control_index": config["source_controls_indices"][index],
            "mask": mask,
            "exponent": group_exponent,
            "seed_x": str(seed),
            "orbit_x": str(frobenius(seed, group_exponent)),
            "source_q": encode_pair(q),
            "frobenius_q": encode_pair([frobenius(int(c), group_exponent) for c in q]),
        })
        if time.monotonic() - started > config["producer_limit_seconds"]:
            raise TimeoutError("frozen producer wall limit")

    negative = []
    for index in range(config["negative_field_inputs"]):
        material = f"{config['negative_field_domain']}|{index}".encode()
        word = int.from_bytes(hashlib.sha256(material).digest()[:17], "big") & FIELD_MASK
        witnesses, reductions = oracle.witnesses(word)
        negative.append({
            "index": index,
            "x": str(word),
            "witnesses": witnesses,
            "span_tests": DEGREE if word else 0,
            "xor_reductions": reductions,
        })
        if time.monotonic() - started > config["producer_limit_seconds"]:
            raise TimeoutError("frozen producer wall limit")
    elapsed_ms = (time.monotonic() - started) * 1000
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if peak_rss > config["peak_rss_limit_bytes"]:
        raise MemoryError("frozen producer peak RSS cap")
    result = {
        "schema": "ecc2k130-orbit-closed-w24-seed-result-v1",
        "candidate_id": None,
        "config_sha256": sha256(CONFIG),
        "producer_source_sha256": {"orbit_seed.py": sha256(HERE / "orbit_seed.py"),
                                   "run.py": sha256(HERE / "run.py")},
        "source_controls_sha256": sha256(source_path),
        "field_element_encoding": "decimal_string_little_endian_polynomial_basis_integer",
        "positive": positive,
        "negative": negative,
        "group": group,
        "counts": {
            "positive_inputs": len(positive),
            "negative_inputs": len(negative),
            "group_controls": len(group),
            "negative_members": sum(bool(row["witnesses"]) for row in negative),
            "span_tests": sum(row["span_tests"] for row in positive + negative),
            "xor_reductions": sum(row["xor_reductions"] for row in positive + negative),
        },
        "producer_wall_ms_exploratory": elapsed_ms,
        "producer_peak_rss_bytes": peak_rss,
        "natural_pdp_yield": None,
        "verified_novel_rank": None,
        "target_online_ms": None,
        "rho_online_ms": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
