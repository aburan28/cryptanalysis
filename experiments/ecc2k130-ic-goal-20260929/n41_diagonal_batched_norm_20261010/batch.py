#!/usr/bin/env python3
"""Batched target-dependent bucket elimination by one global polynomial GCD."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n41_diagonal_double_norm_20261010"
SOURCE = PRIOR / "run.py"
PROTOCOL = HERE / "protocol.json"
INPUT = PRIOR / "input.json"

spec = importlib.util.spec_from_file_location("prior_double_norm", SOURCE)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def phase(name, data):
    path = HERE / "progress.json"
    path.write_text(json.dumps({"phase": name, "data": data,
                                "monotonic_ns": time.monotonic_ns()},
                               sort_keys=True, indent=2) + "\n")


def balanced_product(polynomials):
    level = list(polynomials)
    if not level:
        raise ValueError("empty polynomial product")
    while len(level) > 1:
        level = [level[i] * level[i+1] if i+1 < len(level) else level[i]
                 for i in range(0, len(level), 2)]
    return level[0]


def verify_protocol():
    p = json.loads(PROTOCOL.read_text())
    assert p["status"] == "FROZEN_BEFORE_RUN"
    sources = {"batch": Path(__file__), "freeze": HERE / "freeze.py",
               "prior_run": SOURCE, "prior_input": INPUT,
               "prior_protocol": PRIOR / "protocol.json",
               "prior_result": PRIOR / "result.json",
               "geometry": prior.GEOMETRY,
               "base": Path(prior.old.__file__),
               "pair_oracle": HERE.parent.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py",
               "runtime": HERE / "sage_runtime_info.json"}
    assert {name: sha(path) for name, path in sources.items()} == p["source_sha256"]
    return p


def main(case):
    protocol = verify_protocol()
    input_data = json.loads(INPUT.read_text())
    start = time.monotonic_ns()
    f, curve, geometry, rotations, atom_bases, atoms = prior.source_context()
    pair_lists = [prior.pair_states(f, curve, slot)[0] for slot in atoms]
    field, ring, C, buckets, polynomials, degrees = prior.polynomial_setup(
        f, atom_bases, pair_lists)
    left_all = balanced_product(polynomials[0][s] for s in range(1, 64))
    setup_ns = time.monotonic_ns() - start
    assert left_all.degree() == 4032
    assert all(sorted(set(d.values())) == [64] for d in degrees)
    phase("reusable_setup", {"setup_ns": setup_ns,
                             "left_product_degree": int(left_all.degree()),
                             "peak_rss_bytes": prior.peak_rss()})
    if case == "positive":
        subgroup_target = tuple(input_data["positive_subgroup_target"])
    else:
        assert case == "public"
        subgroup_target = tuple(input_data["public_subgroup_target"])
    online_start = time.monotonic_ns()
    raw_targets = prior.target_preimages(f, curve, subgroup_target)
    admissible = [(i, raw, field.from_integer(f.inv(raw[0])))
                  for i, raw in enumerate(raw_targets)
                  if field.from_integer(f.inv(raw[0])).trace() == 0]
    assert len(admissible) == 2
    if case == "positive":
        control_raw = tuple(input_data["positive_raw_sum"])
        control_index = raw_targets.index(control_raw)
        assert control_index in [i for i, _, _ in admissible]
        admissible = [row for row in admissible if row[0] == control_index]
    phase("target_preimages", {"case": case,
                                "admissible_lift_indices": [x[0] for x in admissible],
                                "online_ns": time.monotonic_ns() - online_start})
    lifts = []
    for lift_index, raw_target, q in admissible:
        right_start = time.monotonic_ns()
        right = prior.make_right_resultants(field, ring, C, buckets[1],
                                            atom_bases[1], q)
        right_all = balanced_product(right[t] for t in range(1, 64))
        right_ns = time.monotonic_ns() - right_start
        assert int(right_all.degree()) == 8064
        phase("global_gcd_start", {"case": case, "lift_index": lift_index,
                                    "right_resultant_ns": right_ns,
                                    "right_product_degree": int(right_all.degree()),
                                    "online_ns": time.monotonic_ns() - online_start,
                                    "peak_rss_bytes": prior.peak_rss()})
        gcd_start = time.monotonic_ns()
        common = left_all.gcd(right_all)
        gcd_ns = time.monotonic_ns() - gcd_start
        phase("global_gcd_done", {"case": case, "lift_index": lift_index,
                                   "common_degree": int(common.degree()),
                                   "global_gcd_ns": gcd_ns,
                                   "online_ns": time.monotonic_ns() - online_start,
                                   "peak_rss_bytes": prior.peak_rss()})
        hits = []
        if common.degree() > 0:
            for s in range(1, 64):
                left_common = polynomials[0][s].gcd(common)
                if left_common.degree() <= 0:
                    continue
                for t in range(1, 64):
                    right_common = right[t].gcd(left_common)
                    if right_common.degree() <= 0:
                        continue
                    witness = prior.exact_bucket_hit(
                        curve, raw_target, pair_lists[0][s], pair_lists[1][t])
                    hits.append({"left_sum_mask": s, "right_sum_mask": t,
                                 "common_degree": int(right_common.degree()),
                                 "exact_witness": witness})
        lifts.append({"lift_index": lift_index, "raw_target": list(raw_target),
                      "right_resultant_ns": right_ns,
                      "global_gcd_ns": gcd_ns,
                      "global_common_degree": int(common.degree()),
                      "bucket_pair_hits": hits,
                      "exact_hits": sum(x["exact_witness"] is not None for x in hits)})
        phase("lift_complete", {"case": case, "lift_index": lift_index,
                                 "global_common_degree": int(common.degree()),
                                 "exact_hits": lifts[-1]["exact_hits"],
                                 "online_ns": time.monotonic_ns() - online_start})
        if time.monotonic_ns() - online_start >= protocol["online_wall_cap_seconds"]*10**9:
            break
    total_online = time.monotonic_ns() - online_start
    status = "COMPLETE" if len(lifts) == len(admissible) else "CENSORED_TIME"
    if case == "positive" and status == "COMPLETE":
        assert any(lift["exact_hits"] > 0 for lift in lifts)
    result = {"status": status, "case": case, "candidate_id": None,
              "subgroup_target": list(subgroup_target),
              "raw_target_count": 4, "admissible_target_lifts": len(admissible),
              "left_product_degree": int(left_all.degree()),
              "reusable_setup_ns": setup_ns,
              "online_wall_ns": total_online,
              "peak_rss_bytes": prior.peak_rss(), "lifts": lifts,
              "protocol_sha256": sha(PROTOCOL),
              "source_sha256": sha(Path(__file__))}
    save(HERE / f"{case}_result.json", result)
    print(json.dumps({"status": status, "case": case,
                      "setup_seconds": setup_ns/1e9,
                      "online_seconds": total_online/1e9,
                      "lifts": [{"index": x["lift_index"],
                                 "common_degree": x["global_common_degree"],
                                 "exact_hits": x["exact_hits"],
                                 "gcd_seconds": x["global_gcd_ns"]/1e9}
                                for x in lifts]}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("positive", "public"):
        raise SystemExit("usage: batch.py positive|public")
    main(sys.argv[1])
