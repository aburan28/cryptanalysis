#!/usr/bin/env sage -python
"""Streaming independent Sage replay of every W18 seed decision."""

import hashlib
import importlib.util
import itertools
import json
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
LIFT = BASE / "n131_w15_coupled_sixpair_20261010/w15_lift.py"
COUNT = 262143


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = {"validator": HERE / "validate.py", "support": SUPPORT,
             "lift": LIFT, "run_protocol": HERE / "protocol.json",
             "runtime": HERE / "sage_runtime_info.json"}
    for index in range(4):
        paths[f"query_{index}"] = HERE / f"query_{index:03d}.json"
        paths[f"receipt_{index}"] = HERE / f"receipt_{index:03d}.json"
    return paths


def save_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def freeze():
    assert not (HERE / "validation_protocol.json").exists()
    assert json.loads((HERE / "sage_runtime_info.json").read_text())["status"] == "verified"
    protocol = {"status": "FROZEN_BEFORE_VALIDATION",
                "seed_count": COUNT, "workers": 1,
                "method": "stream all W18 seed maps once; Sage GF(2^131) products and reverse-pivot linear inverse; replay all three trace-zero coordinates and curve signs for accepted pairs",
                "source_sha256": {name: sha(path) for name, path in sources().items()}}
    save_new(HERE / "validation_protocol.json", protocol)
    print("validation frozen")


def enc(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def halftrace(value, field):
    result = field.zero()
    for _ in range(66):
        result += value
        value = value**4
    return result


def linear_inverse(field, seed, basis, seed_mask):
    pivots = {}
    kernel = None
    for index, basis_value in enumerate(basis):
        value = enc(basis_value * basis_value + seed * basis_value)
        source_mask = 1 << index
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = (value, source_mask)
                break
            vector, represented = pivots[bit]
            value ^= vector
            source_mask ^= represented
        if value == 0:
            assert kernel is None
            kernel = source_mask
    assert len(pivots) == 17 and kernel == seed_mask
    return sorted(pivots.items(), reverse=True)


def invert(pivots, value):
    mask = 0
    for bit, (vector, represented) in pivots:
        if value >> bit & 1:
            value ^= vector
            mask ^= represented
    return mask if value == 0 else None


def group_replay(hit, coordinate, rotation, columns):
    spec = importlib.util.spec_from_file_location("w18_group_lift", LIFT)
    lift = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lift)
    _, field, curve, _, _ = lift.source()
    half = lift.run.prior.inverse_module.prior.half_trace
    basis_w = [1 << i for i in range(1, 19)]
    basis_u = [half(field, w) for w in basis_w]
    a, b = hit["masks"]
    assert (columns[a], columns[b]) == tuple(hit["columns"])
    points = [lift.frobenius(field, lift.atom(field, curve, basis_w, basis_u, mask), rotation)
              for mask in (a, b)]
    accepted = 0
    for signs in itertools.product((0, 1), repeat=2):
        left, right = [curve.neg(point) if sign else point
                       for point, sign in zip(points, signs)]
        if lift.reciprocal(field, curve.add(left, right)) == coordinate:
            accepted += 1
    assert accepted > 0
    return accepted


def main():
    protocol = json.loads((HERE / "validation_protocol.json").read_text())
    assert protocol["status"] == "FROZEN_BEFORE_VALIDATION"
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert not (HERE / "validation.json").exists()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "z", modulus=t**131 + t**13 + t**2 + t + 1)
    basis = [field.from_integer(1 << i) for i in range(1, 19)]
    hbasis = [enc(halftrace(value * value, field)) for value in basis]
    columns = {int(mask): int(column) for mask, column in
               (line.split() for line in SUPPORT.read_text().splitlines())}
    assert len(columns) == 131307 and len(set(columns.values())) == 131068
    cases = json.loads((HERE / "protocol.json").read_text())["cases"]
    raw = [json.loads((HERE / f"query_{i:03d}.json").read_text()) for i in range(4)]
    state = []
    for case, result in zip(cases, raw):
        c = field.from_integer(case["coordinate"])
        for _ in range((131 - case["rotation"]) % 131):
            c *= c
        assert enc(c**(2**case["rotation"])) == case["coordinate"]
        c2 = c*c
        hc = halftrace(c2, field)
        trace = hc*hc + hc + c2
        assert trace in (field.zero(), field.one())
        assert int(trace) == result["trace_bit"]
        state.append({"coordinate": c, "c2": c2, "hc": hc,
                      "inverse": 1/c, "trace": int(trace),
                      "image_hits": 0, "source_hits": 0,
                      "column_rejects": 0, "hits": []})
    hseeds = [0] * (COUNT + 1)
    began = time.monotonic_ns()
    for seed_mask in range(1, COUNT + 1):
        low = seed_mask & -seed_mask
        hseeds[seed_mask] = hseeds[seed_mask ^ low] ^ hbasis[low.bit_length() - 1]
        seed = field.from_integer(seed_mask << 1)
        hs = field.from_integer(hseeds[seed_mask])
        assert hs*hs + hs == seed*seed
        inverse = linear_inverse(field, seed, basis, seed_mask)
        for query in state:
            if query["trace"]:
                continue
            for branch in (0, 1):
                product = (query["hc"] + hs + field.from_integer(branch)) * query["inverse"]
                mask = invert(inverse, enc(product))
                if mask is None:
                    continue
                query["image_hits"] += 1
                a, b = sorted((mask, mask ^ seed_mask))
                if a not in columns or b not in columns:
                    continue
                query["source_hits"] += 1
                if columns[a] == columns[b]:
                    query["column_rejects"] += 1
                    continue
                assert field.from_integer(a << 1) * field.from_integer(b << 1) == product
                c = query["coordinate"]
                assert (field.one() + product*product)*c*c + product*c + seed*seed == 0
                query["hits"].append((seed_mask, a, b, enc(product)))
        if seed_mask % 32768 == 0:
            print("validated seeds", seed_mask, "elapsed_s", (time.monotonic_ns()-began)/1e9,
                  flush=True)
    rows = []
    for case, query, result in zip(cases, state, raw):
        native = {(hit["seed"], *hit["masks"],
                   hit["product"][0] | hit["product"][1] << 64 | hit["product"][2] << 128)
                  for hit in result["hits"]}
        assert set(query["hits"]) == native
        assert query["image_hits"] == result["linear_image_hits"]
        assert query["source_hits"] == result["source_pair_hits"]
        assert query["column_rejects"] == result["column_rejects"]
        assert result["seeds_checked"] == (0 if query["trace"] else COUNT)
        signs = sum(group_replay(hit, case["coordinate"], case["rotation"], columns)
                    for hit in result["hits"])
        rows.append({"name": case["name"], "all_seed_decisions_replayed": result["seeds_checked"],
                     "linear_image_hits": query["image_hits"],
                     "accepted_source_pairs": len(query["hits"]),
                     "group_sign_matches": signs})
    output = {"status": "verified", "curve_id": "EC1N131Ckb1heb5f1998f20b",
              "seed_count": COUNT, "sage_scan_ns_exploratory": time.monotonic_ns() - began,
              "source_sha256": protocol["source_sha256"],
              "validation_protocol_sha256": sha(HERE / "validation_protocol.json"),
              "cases": rows}
    save_new(HERE / "validation.json", output)
    print("verified", len(rows), "cases")


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else main()
