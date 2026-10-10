#!/usr/bin/env python3
"""Enumerate the exact rational W14 s=t raw pair-output x buckets."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "prepare_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("support", SUPPORT),
                       ("control", CONTROL), ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "roots.json").exists()
    print("START_ROOT_BUILD", flush=True)
    started = time.monotonic_ns()
    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    field = GF(2**131, name="t", modulus=t0**131+t0**13+t0**2+t0+1)

    def decode(value):
        return field(binary([(value >> i) & 1 for i in range(131)]))

    def encode(value):
        return int(sum(int(bit) << i for i, bit in enumerate(value.polynomial().list())))

    support = {}
    for line in SUPPORT.read_text().splitlines():
        mask, column = map(int, line.split())
        assert mask not in support and 0 < mask < 2**14 and column >= 0
        support[mask] = column
    assert len(support) == 8220
    seed = field.gen()
    assert encode(seed) == 2
    reciprocal_roots = []
    allowed_pairs = 0
    pair_start = time.monotonic_ns()
    for mask in range(1, 2**14):
        other = mask ^ 1
        if (mask >= other or mask not in support or other not in support or
                support[mask] == support[other]):
            continue
        wa = decode(mask << 1)
        wb = decode(other << 1)
        assert wa + wb == seed
        product = wa * wb
        a = 1 + product**2
        b = product
        c = seed**2
        assert a and b
        alpha = a*c/(b*b)
        half = field.zero()
        power = alpha
        for _ in range(66):
            half += power
            power = power**4
        assert half**2+half == alpha
        scale = b/a
        for root in (scale*half, scale*(half+1)):
            assert root and a*root**2+b*root+c == 0
            reciprocal_roots.append(root)
        allowed_pairs += 1
        if allowed_pairs % 256 == 0:
            assert time.monotonic_ns()-started < protocol["wall_cap_seconds"]*10**9
    pair_ns = time.monotonic_ns()-pair_start
    assert allowed_pairs == 2062 and len(reciprocal_roots) == 4124
    assert len(set(reciprocal_roots)) == 4124

    invert_start = time.monotonic_ns()
    prefix = []
    product = field.one()
    for root in reciprocal_roots:
        prefix.append(product)
        product *= root
    inverse_product = ~product
    raw_x = [field.zero()] * len(reciprocal_roots)
    for i in range(len(reciprocal_roots)-1, -1, -1):
        raw_x[i] = inverse_product*prefix[i]
        inverse_product *= reciprocal_roots[i]
    assert inverse_product == 1
    assert all(a*b == 1 for a, b in zip(raw_x, reciprocal_roots))
    inversion_ns = time.monotonic_ns()-invert_start

    rotate_start = time.monotonic_ns()
    rotations = {}
    for rotation in protocol["rotations"]:
        values = []
        for value in raw_x:
            for _ in range(rotation):
                value *= value
            values.append(encode(value))
        values.sort()
        assert len(values) == len(set(values)) == 4124
        rotations[str(rotation)] = values
    rotation_ns = time.monotonic_ns()-rotate_start
    control = json.loads(CONTROL.read_text())["panels"]["131"]
    assert control["rotations"] == protocol["rotations"]
    for rotation, reciprocal in zip(protocol["rotations"], control["pair_outputs_reciprocal"]):
        assert encode(~decode(reciprocal)) in rotations[str(rotation)]
    result = {"status": "COMPLETE_EXACT_ROOTS", "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "target_count": 0,
              "source_sha256": sha(Path(__file__)), "protocol_sha256": sha(protocol_path),
              "curve_id": control["curve_id"], "source_dimension": 14, "seed_sum": 2,
              "allowed_source_pairs": allowed_pairs, "distinct_raw_pair_x_per_rotation": 4124,
              "rotations": rotations,
              "positive_raw_sum_x": control["raw_sum"][0],
              "control_z": control["trace_zero_control_z"],
              "pair_root_build_ns": pair_ns, "batch_inversion_ns": inversion_ns,
              "rotation_ns": rotation_ns,
              "setup_ns": time.monotonic_ns()-started,
              "peak_self_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                                     (1 if sys.platform == "darwin" else 1024)}
    assert result["setup_ns"] < protocol["wall_cap_seconds"]*10**9
    assert result["peak_self_rss_bytes"] < protocol["rss_cap_bytes"]
    with (HERE / "roots.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "allowed_pairs": allowed_pairs,
                      "setup_ns": result["setup_ns"], "rss": result["peak_self_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
