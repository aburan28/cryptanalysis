#!/usr/bin/env python3
"""Build `inputs/power_prior.json` from archived Tier 1 receipts on main (run once, before freezing).

Sources (all from `koblitz-n83-state-fold-20261015/run_github_38819494806/`,
run 38819494806, one ubuntu-24.04 runner):

* `panel/runs.jsonl`: per-point setup and online times of the 16 cold
  points for the unfolded combined producer (cB) and the folded one (cF);
* `panel/runs/000{41,42,103,104}.stdout.txt`: the four rank-stage processes'
  raw records (kB: B's rank stage, full scan, left-major, unfolded; kN:
  lift_scan, Feistel, folded, no pipeline), with every attempt's ns.

The per-attempt files are not in a sparse checkout of the receipt; pass the
directory holding them (`git show origin/main:<path>` of each) with
`--raw-dir`. Their sha256 digests are recorded in the prior.

The prior also records two measured online factors from main's other
receipts, used by `power_check.py` to model the stack: the probe pipeline
(1.4001, run 38822490448, combined / pipeline) and the 16-byte slots
(1.0581, run 38829449594, pP / pK), and the state fold's online cost
(cB / cF online 0.9490, run 38819494806).
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLD = HERE.parent / "koblitz-n83-state-fold-20261015" / "run_github_38819494806" / "panel"
OUT = HERE / "inputs" / "power_prior.json"
RANK_FILES = {"kN": ("00041", "00103"), "kB": ("00042", "00104")}


def raw(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith("raw_b64="):
            return json.loads(base64.b64decode(line[len("raw_b64="):]))
    raise ValueError("no raw record in " + str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (FOLD / "runs.jsonl").read_text().splitlines() if line.strip()]
    cold = {}
    for row in rows:
        if row["arm"] in ("cB", "cF") and row["status"] == "valid":
            cold.setdefault(row["arm"], {})[row["point_id"]] = {
                "setup_ms": float(row["fields"]["setup_ms"]), "online_ms": float(row["fields"]["online_ms"])}
    rank, digests = {}, {}
    for arm, serials in RANK_FILES.items():
        rank[arm] = []
        for serial in serials:
            path = args.raw_dir / (serial + ".stdout.txt")
            digests[serial + ".stdout.txt"] = hashlib.sha256(path.read_bytes()).hexdigest()
            record = raw(path)
            summary = next(r for r in record["records"] if r.get("kind") == "compact_orbit_dlp_summary")
            rank[arm].append({"serial": int(serial), "rank_stage_ms": summary["timing_ms"]["rank_stage"],
                              "attempt_ns": summary["rank_attempt_ns"]})
    prior = {"schema": 1, "source_run": 38819494806,
             "source_runs_jsonl_sha256": hashlib.sha256((FOLD / "runs.jsonl").read_bytes()).hexdigest(),
             "source_raw_sha256": digests,
             "cold": cold, "rank": rank,
             "factors": {"probe_pipeline_online": 1.4001, "compact_slot_online": 1.0581,
                         "fold_online_cB_over_cF": 0.9490,
                         "compact_slot_setup_pP_over_pK": 51081.0 / 49288.0},
             "factor_sources": {"probe_pipeline_online": "run 38822490448, R_m combined / pipeline",
                                "compact_slot_online": "run 38829449594, pP / pK online",
                                "fold_online_cB_over_cF": "run 38819494806, online cB / cF",
                                "compact_slot_setup_pP_over_pK": "run 38829449594, mean setup pP / pK"}}
    OUT.write_text(json.dumps(prior, indent=1, sort_keys=True) + "\n")
    print(str(OUT))


if __name__ == "__main__":
    main()
