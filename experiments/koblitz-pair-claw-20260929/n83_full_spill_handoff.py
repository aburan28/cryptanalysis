#!/usr/bin/env python3
"""One-shot Q1060-to-Q1062 handoff after an exact zero-hit terminal receipt.

This watcher never removes a marker or retries a failed run. The Q1062
campaign performs its own exclusive-start and resource preflight checks.
"""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
Q1060 = RUNS / (
    "n83_spill_lowmem_k48194_chunk_M28_R30_tstart268435456_"
    "qstart1073741824_b20_h10_rb8.json")
Q1062 = RUNS / (
    "n83_full_spill_k48194_chunk_M31_R30_tstart0_"
    "qstart1073741824_b20_h10_rb8.json")
REPORT = RUNS / "n83_full_spill_handoff_from_q1060.json"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
CAMPAIGN = HERE / "n83_full_spill_campaign.py"
WAIT_SECONDS = 6 * 3600


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-seconds", type=int, default=WAIT_SECONDS)
    args = parser.parse_args()
    assert 0 < args.wait_seconds <= WAIT_SECONDS
    assert not REPORT.exists(), "refusing to overwrite handoff report"
    marker = Q1060.with_suffix(".started.json")
    assert marker.exists() or Q1060.exists(), "Q1060 run not found"
    started = json.loads(marker.read_text()) if marker.exists() else None
    if started is not None:
        assert started["proposal_id"] == "Q1060"
        assert started["candidate_id"] is None
        assert started["curve_id"] == "EC1N83Ckb1h876c2921cb64"
        assert started["isogeny"] == "none"
        assert started["table_start"] == 1 << 28
        assert started["query_start"] == 1 << 30
        assert started["table_descriptors"] == 1 << 28
        assert started["query_representatives"] == 1 << 30
    deadline = time.monotonic() + args.wait_seconds
    began = now()
    while not (Q1060.exists() and not marker.exists()):
        if time.monotonic() >= deadline:
            raise TimeoutError("Q1060 did not reach a cleared terminal receipt")
        time.sleep(30)
    completed = json.loads(Q1060.read_text())
    assert completed["proposal_id"] == "Q1060"
    assert completed["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert completed["isogeny"] == "none"
    report = {
        "kind": "n83_q1060_to_q1062_one_shot_handoff",
        "proposal_id": "Q1062", "candidate_id": None,
        "curve_id": completed["curve_id"], "isogeny": "none",
        "began_waiting_at_utc": began,
        "Q1060_terminal_receipt_sha256": sha(Q1060),
        "Q1060_terminal_kind": completed["kind"],
        "Q1060_verified_dlp": completed.get(
            "verified_public_target_quotient_table_dlp", False),
        "Q1060_exact_hit_queries": (completed.get("native_result") or {}).get(
            "exact_hit_queries"),
        "Q1062_launch_attempted": False,
        "Q1062_terminal_receipt_sha256": None,
        "handoff_source_sha256": sha(Path(__file__)),
    }
    eligible = (completed["kind"] ==
                "n83_public_target_signed_x_query_k48194_exact_replay_chunk"
                and completed.get("native_result", {}).get(
                    "exact_hit_queries") == 0
                and not completed["verified_public_target_quotient_table_dlp"])
    if not eligible:
        report["outcome"] = "Q1060_not_exact_zero_hit; Q1062_not_launched"
        report["finished_at_utc"] = now()
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
        return
    assert completed["factor_base"]["enumerated_set_sha256"] == (
        "7e3c95f988225da1d586578529953ad61ae5ed62ca740eb92c2aea6d841a5a02")
    assert not Q1062.exists(), "Q1062 first full range already has a receipt"
    command = [str(SAGE), "-python", str(CAMPAIGN), "--run-next"]
    report["Q1062_launch_attempted"] = True
    report["Q1062_command"] = command
    report["Q1062_launch_attempted_at_utc"] = now()
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    result = subprocess.run(command, cwd=HERE.parents[1], check=False)
    report["Q1062_campaign_returncode"] = result.returncode
    report["Q1062_terminal_receipt_sha256"] = (
        sha(Q1062) if Q1062.exists() else None)
    report["outcome"] = (
        "Q1062_campaign_completed" if result.returncode == 0 else
        "Q1062_campaign_refused_or_failed")
    report["finished_at_utc"] = now()
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
