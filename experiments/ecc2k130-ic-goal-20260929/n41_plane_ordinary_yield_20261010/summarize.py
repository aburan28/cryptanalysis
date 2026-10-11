"""Summarize the audited secondary panel without converting it to an IC speedup."""

import hashlib
import json
import math
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "summary_protocol.json").read_text())
    paths = {"script": Path(__file__), "panel": HERE / "panel_result.json",
             "audit": HERE / "panel_sage_audit.json", "query_protocol": HERE / "panel_protocol.json",
             "public": HERE / "public_targets.json"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    panel = json.loads(paths["panel"].read_text())
    audit = json.loads(paths["audit"].read_text())
    assert panel["status"] == "COMPLETE_PANEL"
    assert audit["status"] == "PASS_INDEPENDENT_SAGE_N41_PLANE_ORDINARY_PANEL"
    rows = panel["rows"]
    n = len(rows)
    k = sum(row["status"] == "VERIFIED_SCALAR" for row in rows)
    assert n == audit["target_count"] == 16 and k == audit["verified_scalar_count"] == 6
    assert all(row["status"] in ("VERIFIED_SCALAR", "EXHAUSTED_NO_RELATION") for row in rows)
    z = 1.959963984540054
    p = k / n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half_width = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator

    def stats(status):
        selected = [row for row in rows if row["status"] == status]
        online = [row["online_ns"] for row in selected]
        return {"count": len(selected), "online_median_ns": int(statistics.median(online)),
                "online_min_ns": min(online), "online_max_ns": max(online),
                "setup_median_ns": int(statistics.median(row["setup_ns"] for row in selected)),
                "accepted_probes_total": sum(row["accepted_probes"] for row in selected)}

    result = {"status": "PASS_AUDITED_N41_ORDINARY_YIELD_PANEL",
              "curve_id": "EC1N41Ckb1h023d9a38bbf7", "candidate_id": None,
              "workload_kind": "secondary_method_selection_panel_after_completed_single_point_run",
              "source_policy": {"slot_rotations": [0,5,10,10,20,20], "offset_mask": 57},
              "target_count": n, "verified_scalar_count": k,
              "exhausted_no_relation_count": n-k,
              "empirical_yield": k/n,
              "wilson_95_interval_descriptive": [center-half_width, center+half_width],
              "verified": stats("VERIFIED_SCALAR"),
              "exhausted": stats("EXHAUSTED_NO_RELATION"),
              "total_online_ns_all_targets": sum(row["online_ns"] for row in rows),
              "peak_rss_bytes_across_runs": max(row["peak_rss_bytes"] for row in rows),
              "total_group_matches": sum(row["group_hits"] for row in audit["rows"]),
              "total_column_rejections": sum(row["column_rejects"] for row in audit["rows"]),
              "novel_rank": None,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(HERE / "summary_protocol.json")}
    with (HERE / "summary.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"], "verified": k,
                      "targets": n, "interval": result["wilson_95_interval_descriptive"]}))


if __name__ == "__main__":
    main()
