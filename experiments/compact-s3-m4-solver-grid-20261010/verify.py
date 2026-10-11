#!/usr/bin/env python3
"""Verify Q1424 frozen sources, exact XCNFs, 24 solver logs and 12 rows."""

import gzip
import hashlib
import json
from pathlib import Path
import re

from run import CASE, HERE, OLD, N83_VARIANTS, VARIANTS, check_freeze


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect_log(meta):
    archive = HERE / meta["path"]
    assert sha(archive.read_bytes()) == meta["archive_sha256"]
    data = gzip.decompress(archive.read_bytes())
    assert sha(data) == meta["sha256"] and len(data) == meta["bytes"]
    return data.decode("utf-8", "replace")


def check_solver(result, expected_status, cap):
    stdout = inspect_log(result["logs"]["stdout"])
    stderr = inspect_log(result["logs"]["stderr"])
    assert not stderr.strip(), stderr[-1000:]
    statuses = re.findall(r"^s\s+(\S+)", stdout, re.M)
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", stdout, re.M)
    assert result["status"] == expected_status and result["stop_reason"] is None
    assert result["search_began"]
    assert result["conflicts"] == int(conflicts[-1])
    if expected_status == "SAT":
        assert statuses[-1] == "SATISFIABLE" and result["return_code"] == 10
    else:
        assert statuses[-1] == "INDETERMINATE"
        assert result["return_code"] == 15 and result["conflicts"] >= cap


def main():
    frozen = check_freeze()
    rows = []
    for n, case in CASE.items():
        ordinary_archive = OLD / case["ordinary_formula"]
        ordinary_data = gzip.decompress(ordinary_archive.read_bytes())
        control_archive = (OLD / f"q1419_partial_pin/runs/n{n}_full_lock"
                           / "system.xcnf.gz")
        control_data = gzip.decompress(control_archive.read_bytes())
        for variant in VARIANTS if n == 53 else N83_VARIANTS:
            path = HERE / f"n{n}_{variant}.json"
            row = json.loads(path.read_text())
            assert row["proposal_id"] == "Q1424" and row["candidate_id"] is None
            assert row["isogeny"] == "none"
            assert row["freeze_sha256"] == sha((HERE / "freeze.json").read_bytes())
            assert (row["curve_id"], row["workload_id"],
                    row["factor_base_actual_B"],
                    row["factor_base_folded_columns_K"],
                    row["factor_base_enumerated_set_sha256"]) == (
                case["curve_id"], case["workload_id"], case["B"],
                case["K"], case["base_digest"])
            assert tuple(row["solver_flags"]) == VARIANTS[variant]
            assert row["ordinary_formula_sha256"] == sha(ordinary_data)
            assert row["ordinary_formula_archive_sha256"] == sha(
                ordinary_archive.read_bytes())
            assert row["control_formula_sha256"] == sha(control_data)
            assert row["control_formula_archive_sha256"] == sha(
                control_archive.read_bytes())
            check_solver(row["control"], "SAT",
                         frozen["control_limits"]["max_conflicts"])
            check_solver(row["ordinary"], "BOUNDED_UNKNOWN",
                         frozen["ordinary_limits"]["max_conflicts"])
            assert row["control_model_checked"] is not None
            assert row["ordinary_model_checked"] is None
            assert row["ordinary_relation_check"] is None
            assert row["verified_natural_relation_count"] == 0
            rows.append({"n": n, "variant": variant,
                         "control_status": row["control"]["status"],
                         "ordinary_status": row["ordinary"]["status"],
                         "ordinary_conflicts": row["ordinary"]["conflicts"],
                         "ordinary_wall_seconds": row["ordinary"]["wall_seconds"],
                         "ordinary_sampled_peak_rss_bytes": row["ordinary"][
                             "sampled_peak_rss_bytes"],
                         "receipt_sha256": sha(path.read_bytes())})
    result = {"schema": "q1424-grid-archive-verification-v1",
              "status": "PASS", "freeze_sha256": sha((HERE / "freeze.json").read_bytes()),
              "rows": rows, "verifier_sha256": sha(Path(__file__).read_bytes())}
    (HERE / "verification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rows": len(rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
