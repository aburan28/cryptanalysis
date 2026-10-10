#!/usr/bin/env python3
"""Exact prefix-rectangle rejection and first collision widths."""

import hashlib
import json
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def screen(f, item, k):
    low = (1 << k) - 1
    a, b, t = item["a"] & ~low, item["b"] & ~low, item["t"]
    columns = run.variation_columns(f, a, b, t, k)
    dimension = run.rank(columns)
    consistent = run.rank(columns + [run.s3(f, a, b, t)]) == dimension
    return {"rank": dimension, "consistent": consistent}


def main():
    output = HERE / "followup_result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "followup_protocol.json").read_text())
    for name, path in [("source", Path(__file__)), ("run", HERE / "run.py"),
                       ("result", HERE / "result.json"), ("geometry", run.GEOMETRY)]:
        if sha(path) != protocol["sha256"][name]:
            raise ValueError("frozen digest mismatch: " + name)
    record = json.loads((HERE / "result.json").read_text())
    geometry = json.loads(run.GEOMETRY.read_text())["n41"]
    f41 = run.Field(41, [0, 3])
    domains = [run.pair_states(f41, geometry["point_rows_by_unique_rotation"][str(r)])
               for r in [20, 30]]
    census = []
    for domain in domains:
        xs = {state[0][0] for state in domain}
        by_width = run.prefix_census(xs, range(41))
        first = next(k for k in range(41)
                     if by_width[str(k)]["non_singleton_prefixes"])
        census.append({"first_nonsingleton_low_bits": first,
                       "at_first": by_width[str(first)],
                       "at_full_rank_12": by_width["12"]})
    cases = {}
    for n, f, ks in [(41, f41, protocol["n41_low_bits"]),
                     (131, run.Field(131, [0, 1, 2, 13]), protocol["n131_low_bits"])]:
        section = "n" + str(n)
        items = record[section]["cases"]
        per_k = {}
        for k in ks:
            checks = [screen(f, item, k) for item in items]
            if any(check["rank"] != item["ranks"][str(k)]
                   for check, item in zip(checks, items)):
                raise AssertionError("prefix-base rank differs from full-base rank")
            per_k[str(k)] = {
                "ranks": [check["rank"] for check in checks],
                "positive_control_pass": checks[0]["consistent"] if n == 41 else None,
                "nonpositive_cases_rejected": sum(not check["consistent"] for check in
                                                  (checks[1:] if n == 41 else checks)),
                "nonpositive_cases_total": len(checks) - (n == 41),
            }
        cases[section] = per_k
    result = {"status": "COMPLETE_DIAGNOSTIC", "source_sha256": sha(Path(__file__)),
              "protocol_sha256": sha(HERE / "followup_protocol.json"),
              "base_result_sha256": sha(HERE / "result.json"),
              "n41_collision_census": census, "prefix_screens": cases,
              "target_count": 0, "candidate_id": None}
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "first_collisions":
                      [x["first_nonsingleton_low_bits"] for x in census],
                      "n41_rejections": {k: v["nonpositive_cases_rejected"]
                                         for k, v in cases["n41"].items()},
                      "n131_rejections": {k: v["nonpositive_cases_rejected"]
                                          for k, v in cases["n131"].items()}}))


if __name__ == "__main__":
    main()
