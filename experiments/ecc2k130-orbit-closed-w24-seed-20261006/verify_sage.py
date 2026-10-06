#!/usr/bin/env sage -python
"""Independent Sage replay of the implicit W24 seed and group controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = HERE / "CONFIG.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    config = json.loads(CONFIG.read_text())
    result = json.loads(args.result.read_text())
    runtime = json.loads(args.runtime_info.read_text())
    assert runtime["status"] == "verified"
    assert result["config_sha256"] == sha256(CONFIG)
    assert result["candidate_id"] is None
    assert result["natural_pdp_yield"] is None
    for name, digest in result["producer_source_sha256"].items():
        assert sha256(HERE / name) == digest
    controls_path = ROOT / config["source_controls_path"]
    assert sha256(controls_path) == config["source_controls_sha256"]
    assert result["source_controls_sha256"] == config["source_controls_sha256"]
    controls = json.loads(controls_path.read_text())["source"]

    started = time.monotonic()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    order = int(config["subgroup_order"])

    def decode(word):
        word = int(word)
        assert 0 <= word < (1 << 131)
        return field(sum(t**i for i in range(word.bit_length()) if (word >> i) & 1))

    def encode(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))

    def half_trace(value):
        term = value
        total = value
        for _ in range(65):
            term = term**4
            total += term
        assert total**2 + total == value
        return total

    basis = [field.gen()**j + (field.gen()**j).trace()
             for j in range(1, 25)]
    assert all(int(value.trace()) == 0 for value in basis)

    def seed(mask):
        assert 0 < mask < (1 << 24)
        return sum(basis[j] for j in range(24) if mask & (1 << j))

    def direct_mask(value):
        bits = encode(value)
        mask = bits >> 1
        if not 0 < mask < (1 << 24):
            return None
        return mask if seed(mask) == value else None

    def sage_witnesses(value):
        found = []
        power = value
        for inverse_exponent in range(131):
            mask = direct_mask(power)
            if mask is not None:
                found.append({"exponent": (-inverse_exponent) % 131,
                              "mask": mask})
            power = power**2
        assert power == value
        return sorted(found, key=lambda item: item["exponent"])

    assert len(result["positive"]) == 56
    for row in result["positive"]:
        control = controls[row["control_index"]]
        assert row["mask"] == control["mask"]
        assert row["planted_exponent"] in config["frobenius_exponents"]
        value = decode(row["orbit_x"])
        assert value == seed(row["mask"]) ** (1 << row["planted_exponent"])
        assert row["witnesses"] == sage_witnesses(value)
        assert {"exponent": row["planted_exponent"], "mask": row["mask"]} in row["witnesses"]
        assert row["span_tests"] == 131
        assert row["xor_reductions"] >= 0
        if time.monotonic() - started > config["independent_sage_limit_seconds"]:
            raise TimeoutError("frozen Sage wall limit")

    assert len(result["negative"]) == config["negative_field_inputs"]
    negative_members = 0
    for row in result["negative"]:
        material = f"{config['negative_field_domain']}|{row['index']}".encode()
        word = int.from_bytes(hashlib.sha256(material).digest()[:17], "big") & ((1 << 131) - 1)
        assert int(row["x"]) == word
        expected = sage_witnesses(decode(word))
        assert row["witnesses"] == expected
        negative_members += bool(expected)
        assert row["span_tests"] == (131 if word else 0)
        if time.monotonic() - started > config["independent_sage_limit_seconds"]:
            raise TimeoutError("frozen Sage wall limit")

    assert len(result["group"]) == 8
    for index, row in enumerate(result["group"]):
        assert row["control_index"] == config["source_controls_indices"][index]
        control = controls[row["control_index"]]
        assert row["mask"] == control["mask"]
        exponent = config["frobenius_exponents"][index % 7]
        assert row["exponent"] == exponent
        w = seed(row["mask"])
        orbit_w = w ** (1 << exponent)
        assert encode(w) == int(row["seed_x"])
        assert encode(orbit_w) == int(row["orbit_x"])
        assert [int(c) for c in row["source_q"]] == control["source"]
        q = curve([decode(c) for c in row["source_q"]])
        assert not q.is_zero() and (order * q).is_zero()
        q_orbit = curve([decode(c) for c in row["frobenius_q"]])
        assert q_orbit == curve([q[0] ** (1 << exponent),
                                 q[1] ** (1 << exponent)])
        u = half_trace(orbit_w)
        assert u not in (0, 1)
        x = 1 + 1 / u
        rhs = x + 1 / (x * x)
        assert int(rhs.trace()) == 0
        point = curve([x, x * half_trace(rhs)])
        assert 4 * point == q_orbit
        assert sage_witnesses(orbit_w) == next(
            positive["witnesses"] for positive in result["positive"]
            if positive["control_index"] == row["control_index"]
            and positive["planted_exponent"] == exponent
        )
        if time.monotonic() - started > config["independent_sage_limit_seconds"]:
            raise TimeoutError("frozen Sage wall limit")

    assert result["counts"]["positive_inputs"] == len(result["positive"])
    assert result["counts"]["negative_inputs"] == len(result["negative"])
    assert result["counts"]["group_controls"] == len(result["group"])
    assert result["counts"]["negative_members"] == negative_members
    assert result["counts"]["span_tests"] == sum(
        row["span_tests"] for row in result["positive"] + result["negative"]
    )
    assert result["counts"]["xor_reductions"] == sum(
        row["xor_reductions"] for row in result["positive"] + result["negative"]
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    assert peak <= config["peak_rss_limit_bytes"]
    report = {
        "status": "PASS_INDEPENDENT_SAGE_FIELD_AND_GROUP_REPLAY",
        "result_sha256": sha256(args.result),
        "config_sha256": sha256(CONFIG),
        "source_controls_sha256": sha256(controls_path),
        "verifier_source_sha256": sha256(Path(__file__)),
        "sage_runtime_info_sha256": sha256(args.runtime_info),
        "positive_inputs": len(result["positive"]),
        "negative_inputs": len(result["negative"]),
        "group_controls": len(result["group"]),
        "negative_members": negative_members,
        "verifier_wall_ms_exploratory": (time.monotonic() - started) * 1000,
        "verifier_peak_rss_bytes": peak,
        "candidate_id": None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
