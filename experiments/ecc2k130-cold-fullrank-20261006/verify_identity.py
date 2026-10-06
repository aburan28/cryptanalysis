#!/usr/bin/env python3
"""Independent canonical-ID and exclusive-phase audit of stored manifests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = json.loads((HERE / "runs/verification.json").read_text())


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def check(n):
    base = HERE / "identities"
    candidate = json.loads((base / f"n{n}-candidate.json").read_text())
    workload = json.loads((base / f"n{n}-workload.json").read_text())
    run = json.loads((base / f"n{n}-run.json").read_text())
    audit = next(x for x in AUDIT["cells"] if x["n"] == n)
    cid = candidate.pop("candidate_id")
    curve_id = candidate["curve"].pop("curve_id")
    assert curve_id == f"EC1N{n}Ckb0h{digest({'field': candidate['field'], 'curve': candidate['curve']})}"
    candidate["curve"]["curve_id"] = curve_id
    assert cid == f"IC1N{n}Ckb0fb{audit['factor_base_points']}PDP4mitmRCsampleLAgaussTDdirectISO0h{digest(candidate)}"
    wid = workload.pop("workload_id")
    assert wid == digest(workload)
    assert workload["curve_id"] == curve_id and workload["target_count"] == 1
    assert run["candidate_id"] == cid and run["workload_id"] == wid
    assert run["run_id"] == f"{cid}W{wid}R1"
    assert candidate["factor_base"]["exact_point_set_digest"] == audit["factor_base_point_list_sha256"]
    assert candidate["factor_base"]["actual_usable_subgroup_points_B"] == audit["factor_base_points"]
    assert abs(sum(run["online_exclusive_phase_ms_exploratory"].values()) - run["online_ms_exploratory"]) < 1e-6
    assert run["online_speedup"] is None and run["cold_speedup"] is None
    return {"n": n, "candidate_id": cid, "workload_id": wid, "run_id": run["run_id"], "status": "PASS"}


def main():
    result = {"status": "PASS_CANONICAL_IDS_AND_PHASES", "cells": [check(n) for n in (37, 41)]}
    (HERE / "identities/verification.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(result["status"])


if __name__ == "__main__":
    main()
