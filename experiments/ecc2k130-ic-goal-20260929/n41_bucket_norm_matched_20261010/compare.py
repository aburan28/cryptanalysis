#!/usr/bin/env python3
"""Matched N41 comparison of split-root and quadratic-quotient bucket norms."""

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
PREVIOUS = BASE / "n41_seed_bucket_resultant_20261010"
GEOMETRY = BASE / "n41_two_free_pair_occupancy_20261009/geometry_snapshot.json"
sys.path.insert(0, str(PREVIOUS))
from run import Field, build_bucket, encode  # noqa: E402
from norm_bsgs import bsgs_bucket_norm  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    for name, path in (("source", Path(__file__)), ("helper", PREVIOUS / "run.py"),
                       ("bsgs", PREVIOUS / "norm_bsgs.py"), ("geometry", GEOMETRY),
                       ("prior_audit", PREVIOUS / "audit.json"),
                       ("prior_result", PREVIOUS / "result.json"),
                       ("runtime", HERE / "sage_runtime_info.json")):
        assert sha(path) == protocol["sha256"][name], name
    assert not (HERE / "result.json").exists()
    started = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())["n41"]
    reference = json.loads((PREVIOUS / "result.json").read_text())
    binary = PolynomialRing(GF(2), "t")
    t = binary.gen()
    field = GF(2**41, name="t", modulus=t**41+t**3+1)

    def decode(value):
        return field(binary([(value >> i) & 1 for i in range(41)]))

    ring = PolynomialRing(field, "X")
    x = ring.gen()
    q = decode(protocol["residual"][0])
    f = Field()
    cases = []
    for label in protocol["case_order"]:
        seeds = protocol["cases"][label]
        setup_start = time.monotonic_ns()
        left_keys = build_bucket(f, geometry["point_rows_by_unique_rotation"]["20"], seeds[0])
        right_keys = build_bucket(f, geometry["point_rows_by_unique_rotation"]["30"], seeds[1])
        left = ring.prod(x+decode(value) for value in left_keys)
        right = ring.prod(x+decode(value) for value in right_keys)
        right_roots = [decode(value) for value in right_keys]
        setup_ns = time.monotonic_ns()-setup_start
        expected = next(case for case in reference["cases"] if case["label"] == label)
        observations = []
        norms = {}
        for method in protocol["method_order"]:
            query_start = time.monotonic_ns()
            if method == "split_root":
                factors = [((x+q)**2 * b*b + q*x*b + (q*x)**2 + 1)
                           for b in right_roots]
                norm = ring.prod(factors) % left
                gcd = left.gcd(norm)
            elif method == "bsgs":
                gcd, norm, operations = bsgs_bucket_norm(left, right, q)
            else:
                raise ValueError(method)
            roots = sorted(encode(root) for root, mult in gcd.roots() if mult >= 1)
            elapsed_ns = time.monotonic_ns()-query_start
            assert roots == expected["gcd_roots"]
            norms[method] = norm
            observation = {"method": method, "target_query_ns": elapsed_ns,
                           "gcd_degree": int(gcd.degree()), "gcd_roots": roots}
            if method == "bsgs":
                observation.update(operations)
            observations.append(observation)
        scale = ((x+q)**2)**int(right.degree()) % left
        assert norms["split_root"] == (scale*norms["bsgs"]) % left
        cases.append({"label": label, "seeds": seeds, "left_degree": int(left.degree()),
                      "right_degree": int(right.degree()), "setup_ns": setup_ns,
                      "resultant_norm_identity_mod_left": True, "observations": observations})
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak*1024
    result = {"status": "COMPLETE_MATCHED_BUCKET_PANEL", "candidate_id": None,
              "target_count": 1, "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(protocol_path), "curve_id": geometry["curve_id"],
              "public_target_q": protocol["public_target_q"], "residual": protocol["residual"],
              "cases": cases, "elapsed_wall_ns": time.monotonic_ns()-started,
              "peak_rss_bytes": peak}
    assert result["elapsed_wall_ns"] < protocol["wall_cap_seconds"]*10**9
    assert peak < protocol["rss_cap_bytes"]
    with (HERE / "result.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "cases": [{"label": case["label"],
        "methods": [(row["method"], row["target_query_ns"]) for row in case["observations"]]}
        for case in cases]}))


if __name__ == "__main__":
    main()
