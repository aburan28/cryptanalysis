#!/usr/bin/env python3
"""Frozen full-rank and rank-deficient control for complete inverse."""
import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path

import complete_inverse
import oracle
import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def brute_fixed_sum(candidate, joint, s, p):
    field = candidate.field
    particular = oracle.solve(joint["seed_pivots"], s)
    if particular is None:
        return []
    pairs = []
    for code in oracle.affine_solutions(particular, joint["seed_kernel"]):
        a, b = code & ((1 << oracle.D)-1), code >> oracle.D
        if a not in candidate.valid or b not in candidate.valid:
            continue
        if candidate.columns[a] == candidate.columns[b]:
            continue
        if field.mul(oracle.coordinate(joint["left_w"], a),
                     oracle.coordinate(joint["right_w"], b)) == p:
            pairs.append((a, b))
    return sorted(set(pairs))


def main():
    path = HERE / "complete_protocol.json"
    freeze = json.loads(path.read_text())
    sources = {"runner": Path(__file__), "complete": HERE / "complete_inverse.py",
               "run": HERE / "run.py", "oracle": run.INVERSE / "oracle.py",
               "stage_result": HERE / "result.json", "support": run.SUPPORT}
    assert freeze["sha256"] == {name: sha(source) for name, source in sources.items()}
    assert not (HERE / "complete_result.json").exists()
    start = time.monotonic_ns()
    candidate = oracle.PairOracle(oracle.load_support(run.SUPPORT))
    joint = run.build_joint(candidate)
    stage = json.loads((HERE / "result.json").read_text())
    panel = [(row["kind"], row["z"], row["masks"])
             for row in stage["records"]]
    panel += [("rank_drop_consistent", z, None) for z in (2, 18)]
    panel += [("rank_drop_inconsistent", 3, None),
              ("exceptional", 0, None), ("exceptional", 1, None)]
    rows = []
    for kind, z, masks in panel:
        t0 = time.monotonic_ns()
        pairs, detail = complete_inverse.inverse(candidate, joint, z)
        wall_ns = time.monotonic_ns()-t0
        if kind == "positive":
            assert tuple(masks) in pairs
        if kind == "uniform_field":
            assert pairs == []
        rows.append({"kind": kind, "z": z, "masks": masks,
                     "pairs": pairs, "detail": detail, "wall_ns": wall_ns})
        if (time.monotonic_ns()-start > freeze["wall_cap_seconds"]*10**9):
            raise TimeoutError("complete inverse panel exceeded frozen cap")
    checks = []
    for row in rows:
        if row["kind"] != "positive":
            continue
        a, b = row["masks"]
        s = (oracle.coordinate(joint["left_w"], a) ^
             oracle.coordinate(joint["right_w"], b))
        p = candidate.field.mul(oracle.coordinate(joint["left_w"], a),
                                oracle.coordinate(joint["right_w"], b))
        fast, _ = complete_inverse.fixed_sum_product(candidate, joint, s, p)
        slow = brute_fixed_sum(candidate, joint, s, p)
        assert fast == slow
        checks.append({"kind": "positive", "s": s, "p": p,
                       "pair_count": len(fast)})
    z = 2
    z2 = candidate.field.mul(z, z)
    az = z2 ^ z
    columns = [candidate.field.mul(u, u) for u in joint["sum_u_basis"]] + [
        candidate.field.mul(az, p) for p in joint["product_basis"]]
    pivots, kernel = oracle.echelon(columns)
    particular = oracle.solve(pivots, z2)
    assert particular is not None and len(kernel) == 12
    for i, code in enumerate(oracle.affine_solutions(particular, kernel)):
        if i == freeze["rank_drop_brute_checks"]:
            break
        s, p = complete_inverse.decode_joint(joint, code)
        if s == 0:
            continue
        fast, _ = complete_inverse.fixed_sum_product(candidate, joint, s, p)
        slow = brute_fixed_sum(candidate, joint, s, p)
        assert fast == slow
        checks.append({"kind": "rank_drop", "s": s, "p": p,
                       "pair_count": len(fast)})
    elapsed = time.monotonic_ns()-start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (
        1 if sys.platform == "darwin" else 1024)
    result = {"status": "COMPLETE_EXACT_INVERSE_PANEL",
              "candidate_id": None, "protocol_sha256": sha(path),
              "source_sha256": freeze["sha256"], "rows": rows,
              "fixed_sum_brute_agreements": checks,
              "wall_ns": elapsed, "peak_rss_bytes": rss}
    if elapsed > freeze["wall_cap_seconds"]*10**9:
        result["status"] = "CENSORED_TIME"
    if rss > freeze["rss_cap_bytes"]:
        result["status"] = "CENSORED_MEMORY"
    (HERE / "complete_result.json").write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    print(json.dumps({"status": result["status"],
                      "rank_drop": [row["detail"] for row in rows
                                    if row["kind"].startswith("rank_drop")],
                      "brute_agreements": len(checks),
                      "wall_s": round(elapsed/1e9, 3),
                      "peak_rss_bytes": rss}))


if __name__ == "__main__":
    main()
