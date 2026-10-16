#!/usr/bin/env python3
"""Build the power prior (`inputs/power_prior.json`) from run 38862448935.

The prior is the stacked experiment's archived receipt
(`../koblitz-n83-stacked-20261016/run_github_38862448935/panel`), the
baseline of this experiment measured on the same kind of runner:

* per rank block (rank seeds 101 and 102): the per-attempt ns of kS and of
  its A/A process kSaa. Both ran the same attempts with the same probes, so
  kSaa_i / kS_i is the paired timing noise of one attempt; the stage's
  non-attempt time;
* per cold point (20 points): cold_ms of cS and of its A/A process cSaa.

No timing of this experiment enters the prior. The candidate's effect is a
parameter of `power_check.py`, not read from here; the local profile
(`smoke/`, a diagnostic) only motivates the expected value it reports.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE.parent / "koblitz-n83-stacked-20261016" / "run_github_38862448935" / "panel"
OUT = HERE / "inputs" / "power_prior.json"


def raw(panel, row):
    for line in (panel / row["stdout_file"]).read_text().splitlines():
        if line.startswith("raw_b64="):
            return json.loads(base64.b64decode(line[len("raw_b64="):]))
    raise ValueError("no raw record for serial %d" % row["serial"])


def build(panel):
    rows = [json.loads(line) for line in (panel / "runs.jsonl").read_text().splitlines() if line.strip()]
    blocks, cold = {}, {}
    for row in rows:
        if row.get("status") != "valid":
            continue
        if row["arm"] in ("kS", "kSaa"):
            record = raw(panel, row)
            summary = next(r for r in record["records"] if r.get("kind") == "compact_orbit_dlp_summary")
            attempts = summary["rank_attempt_ns"]
            stage = summary["timing_ms"]["rank_stage"]
            blocks.setdefault(str(row["seed"]), {})[row["arm"]] = {
                "attempt_ns": attempts, "attempt_probes": summary["rank_attempt_probes"],
                "rank_stage_ms": stage, "non_attempt_ms": stage - sum(attempts) / 1e6}
        elif row["arm"] in ("cS", "cSaa") and row["segment"].startswith("C"):
            cold.setdefault(row["point_id"], {})[row["arm"]] = raw(panel, row)["fields"]["cold_ms"]
    for seed, block in blocks.items():
        if block["kS"]["attempt_probes"] != block["kSaa"]["attempt_probes"]:
            raise ValueError("kS and kSaa attempts differ in block %s" % seed)
    return {"schema": 1,
            "source": "koblitz-n83-stacked-20261016/run_github_38862448935 (arms kS, kSaa, cS, cSaa)",
            "runs_jsonl_sha256": hashlib.sha256((panel / "runs.jsonl").read_bytes()).hexdigest(),
            "rank_blocks": {seed: {"kS_attempt_ns": b["kS"]["attempt_ns"], "kSaa_attempt_ns": b["kSaa"]["attempt_ns"],
                                   "kS_non_attempt_ms": b["kS"]["non_attempt_ms"],
                                   "kSaa_non_attempt_ms": b["kSaa"]["non_attempt_ms"]}
                            for seed, b in sorted(blocks.items())},
            "cold_ms": {u: cold[u] for u in sorted(cold) if {"cS", "cSaa"} <= set(cold[u])}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE,
                        help="the archived panel directory (default: the stacked experiment's)")
    args = parser.parse_args()
    OUT.write_text(json.dumps(build(args.archive), sort_keys=True, separators=(",", ":")) + "\n")
    print(str(OUT))


if __name__ == "__main__":
    main()
