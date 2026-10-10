#!/usr/bin/env python3
"""Evaluate the exact N131 W14 bucket norm at all known left roots."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from sage.all import GF, PolynomialRing

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PREVIOUS = BASE / "n131_w14_seed_bucket_norm_20261010"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
sys.path.insert(0, str(PREVIOUS))
from query import product_tree  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value*1024


def make_tree(leaves, guard):
    levels = [leaves]
    while len(levels[-1]) > 1:
        parents = levels[-1]
        levels.append([parents[i]*parents[i+1] if i+1 < len(parents) else parents[i]
                       for i in range(0, len(parents), 2)])
        guard()
    return levels


def evaluate_zero_roots(norm, tree, keys, guard):
    remainders = [norm]
    levels_checked = 0
    for children in reversed(tree[:-1]):
        remainders = [remainders[i//2] % polynomial
                      for i, polynomial in enumerate(children)]
        levels_checked += 1
        guard()
    assert len(remainders) == len(keys)
    assert all(remainder.degree() <= 0 for remainder in remainders)
    return [key for key, remainder in zip(keys, remainders) if remainder == 0], levels_checked


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("prior_source", PREVIOUS / "query.py"),
                       ("roots", PREVIOUS / "roots.json"),
                       ("prior_result", PREVIOUS / "query_result.json"),
                       ("control", CONTROL),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "result.json").exists()
    print("START_N131_ROOT_EVALUATION", flush=True)
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

    roots = json.loads((PREVIOUS / "roots.json").read_text())
    prior = json.loads((PREVIOUS / "query_result.json").read_text())
    control = json.loads(CONTROL.read_text())["panels"]["131"]
    ring = PolynomialRing(field, "X")
    x = ring.gen()
    setup_start = time.monotonic_ns()
    left_keys = roots["rotations"]["26"]
    left_roots = [decode(value) for value in left_keys]
    right_roots = [decode(value) for value in roots["rotations"]["39"]]
    tree = make_tree([x+root for root in left_roots], guard)
    left = tree[-1][0]
    right = product_tree([x+root for root in right_roots], guard)
    assert int(left.degree()) == int(right.degree()) == 4124
    setup_ns = time.monotonic_ns()-setup_start
    setup_rss = peak_rss()
    print(json.dumps({"stage": "SETUP_DONE", "setup_ns": setup_ns,
                      "tree_levels": len(tree), "rss": setup_rss}), flush=True)
    cases = []
    for label in protocol["case_order"]:
        q_start = time.monotonic_ns()
        q = (decode(control["raw_sum"][0]) if label == "positive" else
             ~decode(control["trace_zero_control_z"]))
        qq = q*q
        factors = [ring([qq*b*b+1, q*b, b*b+qq]) for b in right_roots]
        factors_ns = time.monotonic_ns()-q_start
        guard()
        norm_start = time.monotonic_ns()
        norm = product_tree(factors, guard) % left
        norm_ns = time.monotonic_ns()-norm_start
        root_start = time.monotonic_ns()
        hits, levels_checked = evaluate_zero_roots(norm, tree, left_keys, guard)
        root_ns = time.monotonic_ns()-root_start
        expected = next(row for row in prior["cases"] if row["label"] == label)
        assert hits == expected["gcd_roots"]
        cases.append({"label": label, "query_x": int(expected["query_x"]),
                      "norm_remainder_degree": int(norm.degree()),
                      "zero_roots": hits, "remainder_levels_checked": levels_checked,
                      "factor_construction_ns": factors_ns,
                      "balanced_product_and_remainder_ns": norm_ns,
                      "remainder_tree_root_scan_ns": root_ns,
                      "target_query_ns": time.monotonic_ns()-q_start,
                      "peak_self_rss_bytes": peak_rss()})
        print(json.dumps({"stage": "QUERY_DONE", "label": label,
                          "query_ns": cases[-1]["target_query_ns"],
                          "root_scan_ns": root_ns,
                          "zero_roots": len(hits),
                          "rss": cases[-1]["peak_self_rss_bytes"]}), flush=True)
    result = {"status": "COMPLETE_N131_ROOT_EVALUATION_PANEL",
              "proposal_id": protocol["proposal_id"], "candidate_id": None,
              "target_count": 0, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path),
              "prior_result_sha256": sha(PREVIOUS / "query_result.json"),
              "curve_id": control["curve_id"], "seed_sum": 2,
              "pair_outputs_per_rotation": 4124, "setup_ns": setup_ns,
              "setup_peak_self_rss_bytes": setup_rss,
              "tree_levels": len(tree), "cases": cases,
              "elapsed_wall_ns": time.monotonic_ns()-started,
              "peak_self_rss_bytes": peak_rss()}
    guard()
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"],
                      "elapsed_wall_ns": result["elapsed_wall_ns"],
                      "rss": result["peak_self_rss_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
