#!/usr/bin/env sage -python
"""Independent Sage replay of scaled halftrace products on sampled W18 seeds."""

import hashlib
import json
import sys
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n131_w18_allseed_pair_inverse_20261011"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, payload):
    with path.open("x") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def paths():
    result = {"validator": HERE / "validate_sage.py",
              "protocol": HERE / "protocol.json",
              "runtime": HERE / "sage_runtime_info.json",
              "sample_seeds": PRIOR / "sample_protocol.json",
              "prior_validation": PRIOR / "sample_validation.json"}
    for index in range(4):
        result[f"new_query_{index}"] = HERE / f"case_{index:03d}_target_linear.json"
    return result


def halftrace(value, field):
    output = field.zero()
    for _ in range(66):
        output += value
        value = value**4
    return output


def freeze():
    assert not (HERE / "sage_validation_protocol.json").exists()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    protocol = {"status": "FROZEN_BEFORE_SAGE_VALIDATION",
                "method": "on 260 frozen W18 seed masks and four coordinates, compare basis-XOR scaled halftrace products with direct Sage field multiplication",
                "source_sha256": {name: sha(path) for name, path in paths().items()}}
    save_new(HERE / "sage_validation_protocol.json", protocol)
    print("Sage validation frozen")


def run():
    frozen = json.loads((HERE / "sage_validation_protocol.json").read_text())
    assert frozen["source_sha256"] == {name: sha(path) for name, path in paths().items()}
    assert json.loads((PRIOR / "sample_validation.json").read_text())["status"] == \
        "PASS_SAMPLED_SAGE_AND_GROUP_REPLAY"
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "z", modulus=t**131 + t**13 + t**2 + t + 1)
    basis = [field.from_integer(1 << i) for i in range(1, 19)]
    h_basis = [halftrace(value*value, field) for value in basis]
    seeds = json.loads((PRIOR / "sample_protocol.json").read_text())["sample_seed_masks"]
    assert len(seeds) == 260
    cases = json.loads((HERE / "protocol.json").read_text())["cases"]
    checks = []
    for index, case in enumerate(cases):
        raw = json.loads((HERE / f"case_{index:03d}_target_linear.json").read_text())
        c = field.from_integer(case["coordinate"])
        for _ in range((131 - case["rotation"]) % 131):
            c *= c
        hc = halftrace(c*c, field)
        trace = hc*hc + hc + c*c
        assert int(trace) == raw["trace_bit"]
        if trace:
            assert raw["seeds_checked"] == 0
            checks.append({"name": case["name"], "seed_checks": 0, "branch_checks": 0})
            continue
        inverse_c = 1/c
        target_constant = hc*inverse_c
        scaled_basis = [value*inverse_c for value in h_basis]
        branch_checks = 0
        for seed_mask in seeds:
            seed = field.from_integer(seed_mask << 1)
            h_direct = halftrace(seed*seed, field)
            h_linear = field.zero()
            scaled_linear = field.zero()
            for bit in range(18):
                if seed_mask >> bit & 1:
                    h_linear += h_basis[bit]
                    scaled_linear += scaled_basis[bit]
            assert h_linear == h_direct
            assert scaled_linear == h_direct*inverse_c
            p0 = target_constant + scaled_linear
            p1 = p0 + inverse_c
            assert p0 == (hc + h_direct)*inverse_c
            assert p1 == (hc + h_direct + field.one())*inverse_c
            for hit in raw["hits"]:
                if hit["seed"] != seed_mask:
                    continue
                expected = hit["product"][0] | hit["product"][1] << 64 | hit["product"][2] << 128
                assert field.from_integer(expected) in (p0, p1)
            branch_checks += 2
        checks.append({"name": case["name"], "seed_checks": len(seeds),
                       "branch_checks": branch_checks})
        print(case["name"], branch_checks, "branches", flush=True)
    result = {"status": "PASS_SAGE_LINEAR_TARGET_PRODUCTS",
              "sample_seed_count": len(seeds), "cases": checks,
              "source_sha256": frozen["source_sha256"],
              "protocol_sha256": sha(HERE / "sage_validation_protocol.json")}
    save_new(HERE / "sage_validation.json", result)
    print(result["status"])


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
