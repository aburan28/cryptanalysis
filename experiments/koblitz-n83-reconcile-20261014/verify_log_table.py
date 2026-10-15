#!/usr/bin/env python3
"""Re-check every [L_j]G = R_j of a factor-log table in the pinned pure-Python oracle.

Same checks as B's `precompute.py verify` (identity fields against the base
header, range, and every log against its representative), run against the
r770 snapshot's `oracle.py`, independently of the producer that wrote the
table. Exit 3 on any failure. Used once per job on B's archived table before
any timing, and by verify_receipt.py on every table a fresh-rank arm wrote.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshots" / "r770"
AUTOLAB = SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"
BEAT = "koblitz.compact_orbit.n83_single_target"


def oracle_curve():
    sys.path.insert(0, str(AUTOLAB))
    import single_target_panel as panel  # noqa: E402  (pinned harness)
    beats = json.loads((AUTOLAB / "protocol.json").read_text())["beats"]
    return panel.cached_curve(dict(beats[BEAT]["curve_fixture"]))


def verify(table_path, base_path, curve=None):
    table = json.loads(Path(table_path).read_text())
    header = json.loads(Path(base_path).read_text().splitlines()[0])
    curve = curve or oracle_curve()
    reps = header["factor_base_representatives"]
    logs = [int(v) for v in table["logs"]]
    checks = {
        "kind": table.get("kind") == "compact_orbit_factor_log_table",
        "n_a_r": (table.get("n"), table.get("a"), table.get("subgroup_order")) ==
                 (header["n"], header["a"], str(header["subgroup_order"])),
        "base_hash": table.get("base_hash") == header["base_hash"],
        "width": table.get("orbit_columns") == len(reps) == len(logs),
        "range": all(0 < log < curve.r for log in logs),
    }
    bad = [j for j, (log, rep) in enumerate(zip(logs, reps))
           if curve.mul(curve.g, log) != curve.decode([int(rep[0]), int(rep[1])])]
    checks["every_log_maps_G_to_its_representative"] = not bad
    return {"table": str(table_path), "table_sha256": hashlib.sha256(Path(table_path).read_bytes()).hexdigest(),
            "logs_sha256": hashlib.sha256(json.dumps(table["logs"]).encode()).hexdigest(),
            "columns": len(logs), "checks": checks, "bad_columns": bad[:20],
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checker": "oracle.py pure-Python field arithmetic (pinned harness), not the producer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", required=True, type=Path)
    parser.add_argument("--expect-sha256")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = verify(args.table, HERE / protocol["inputs"]["base"])
    if args.expect_sha256 and result["table_sha256"] != args.expect_sha256:
        result["status"] = "FAIL"
        result["checks"]["expected_sha256"] = False
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text, end="")
    if result["status"] != "PASS":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
