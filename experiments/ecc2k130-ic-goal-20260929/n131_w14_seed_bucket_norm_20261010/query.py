#!/usr/bin/env python3
"""Bounded split-root norm on exact N131 W14 raw pair-output buckets."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
NATIVE = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def product_tree(factors, guard):
    assert factors
    while len(factors) > 1:
        factors = [factors[i]*factors[i+1] if i+1 < len(factors) else factors[i]
                   for i in range(0, len(factors), 2)]
        guard()
    return factors[0]


def main():
    protocol_path = HERE / "query_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("roots", HERE / "roots.json"),
                       ("control", CONTROL), ("native", NATIVE),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "query_result.json").exists()
    print("START_N131_SPLIT_ROOT_QUERY", flush=True)
    started = time.monotonic_ns()

    def guard():
        if time.monotonic_ns()-started >= protocol["wall_cap_seconds"]*10**9:
            raise TimeoutError("frozen complete-stage wall cap reached")
        if peak_rss() >= protocol["rss_cap_bytes"]:
            raise MemoryError("frozen RSS cap reached")

    binary = PolynomialRing(GF(2), "t")
    t0 = binary.gen()
    field = GF(2**131, name="t", modulus=t0**131+t0**13+t0**2+t0+1)

    def decode(value):
        return field(binary([(value >> i) & 1 for i in range(131)]))

    def encode(value):
        return int(sum(int(bit) << i for i, bit in enumerate(value.polynomial().list())))

    roots = json.loads((HERE / "roots.json").read_text())
    control = json.loads(CONTROL.read_text())["panels"]["131"]
    native = json.loads(NATIVE.read_text())
    assert roots["status"] == "COMPLETE_EXACT_ROOTS"
    assert roots["distinct_raw_pair_x_per_rotation"] == 4124
    assert control["rotations"] == [26, 39]
    ring = PolynomialRing(field, "X")
    x = ring.gen()
    setup_start = time.monotonic_ns()
    left_roots = [decode(value) for value in roots["rotations"]["26"]]
    right_roots = [decode(value) for value in roots["rotations"]["39"]]
    left = product_tree([x+value for value in left_roots], guard)
    right = product_tree([x+value for value in right_roots], guard)
    assert int(left.degree()) == int(right.degree()) == 4124
    setup_ns = time.monotonic_ns()-setup_start
    setup_rss = peak_rss()
    print(json.dumps({"stage": "SETUP_DONE", "setup_ns": setup_ns,
                      "rss": setup_rss}), flush=True)
    cases = []
    for label in protocol["case_order"]:
        query_start = time.monotonic_ns()
        q = (decode(control["raw_sum"][0]) if label == "positive" else
             ~decode(control["trace_zero_control_z"]))
        qq = q*q
        factors = [ring([qq*b*b+1, q*b, b*b+qq]) for b in right_roots]
        factor_ns = time.monotonic_ns()-query_start
        guard()
        product_start = time.monotonic_ns()
        norm = product_tree(factors, guard) % left
        norm_ns = time.monotonic_ns()-product_start
        gcd_start = time.monotonic_ns()
        common = left.gcd(norm)
        gcd_ns = time.monotonic_ns()-gcd_start
        root_start = time.monotonic_ns()
        hits = sorted(encode(value) for value, multiplicity in common.roots()
                      if multiplicity >= 1)
        roots_ns = time.monotonic_ns()-root_start
        guard()
        native_case = next(row for row in native["rows"]
                           if row["field_degree"] == 131 and
                           row["case"] == ("positive" if label == "positive" else
                                           "trace_zero_control"))
        expected_hits = len(native_case["native"]["hits"])
        assert len(hits) == expected_hits == (1 if label == "positive" else 0)
        if label == "positive":
            expected_x = encode(~decode(control["pair_outputs_reciprocal"][0]))
            assert hits == [expected_x]
            expected_right = ~decode(control["pair_outputs_reciprocal"][1])
            a = decode(expected_x)
            b = expected_right
            assert ((a*b+q*(a+b))**2+q*a*b+1) == 0
        cases.append({"label": label, "query_x": encode(q),
                      "norm_remainder_degree": int(norm.degree()),
                      "gcd_degree": int(common.degree()), "gcd_roots": hits,
                      "factor_construction_ns": factor_ns,
                      "balanced_product_and_remainder_ns": norm_ns,
                      "gcd_ns": gcd_ns, "root_extraction_ns": roots_ns,
                      "target_query_ns": time.monotonic_ns()-query_start,
                      "peak_self_rss_bytes": peak_rss()})
        print(json.dumps({"stage": "QUERY_DONE", "label": label,
                          "query_ns": cases[-1]["target_query_ns"],
                          "gcd_degree": cases[-1]["gcd_degree"],
                          "rss": cases[-1]["peak_self_rss_bytes"]}), flush=True)
    result = {"status": "COMPLETE_N131_PROPOSED_OUTPUT_PANEL",
              "proposal_id": protocol["proposal_id"], "candidate_id": None,
              "target_count": 0, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path), "roots_sha256": sha(HERE / "roots.json"),
              "curve_id": control["curve_id"], "seed_sum": 2,
              "pair_outputs_per_rotation": 4124, "setup_ns": setup_ns,
              "setup_peak_self_rss_bytes": setup_rss, "cases": cases,
              "elapsed_wall_ns": time.monotonic_ns()-started,
              "peak_self_rss_bytes": peak_rss()}
    guard()
    with (HERE / "query_result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "elapsed_wall_ns": result["elapsed_wall_ns"],
                      "peak_self_rss_bytes": result["peak_self_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
