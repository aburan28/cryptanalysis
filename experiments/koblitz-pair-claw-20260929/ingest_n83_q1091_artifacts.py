#!/usr/bin/env python3
"""Download and independently audit newly uploaded Q1091 holdout shards.

The command is safe to rerun while the workflow is live. It keeps downloaded
receipts and audits immutable, and never grants coverage to a partial shard.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from audit_n83_holdout_artifact import audit

HERE = Path(__file__).resolve().parent
PLAN = HERE / "n83_q1091_holdout_m32_continuation_plan.json"
ARCHIVE = HERE / "runs/q1091_raw_ci_37069216423"
RUNTIME = ARCHIVE / "sage_runtime_info.json"
SNAPSHOT = ARCHIVE / "workflow_snapshot.yml"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")
RUN_ID = 37069216423
RUN_HEAD = "26fb34f3ae66ac6442245f24c4eb4c3552f9d328"
ARTIFACT_NAME = re.compile(r"n83-q1091-holdout-M32-R29-shard-(\d+)")
VERIFIER = HERE / "verify_n83_holdout_receipt_sage.py"


def command(args, *, capture=False):
    result = subprocess.run(args, check=True, text=True,
                            capture_output=capture)
    return result.stdout if capture else None


def runtime_is_current():
    archived = json.loads(RUNTIME.read_text())
    current = json.loads(command([str(SAGE), "--runtime-info"], capture=True))
    assert archived["status"] == current["status"] == "verified"
    assert archived["manifest_sha256"] == current["manifest_sha256"], (
        "checked Sage build changed since Q1091 runtime receipt")


def available_artifacts():
    payload = json.loads(command([
        "gh", "api",
        f"repos/aburan28/cryptanalysis/actions/runs/{RUN_ID}/artifacts",
        "-f", "per_page=100", "--method", "GET"], capture=True))
    assert payload["total_count"] <= 64, "unexpected artifact inventory size"
    artifacts = {}
    for item in payload["artifacts"]:
        match = ARTIFACT_NAME.fullmatch(item["name"])
        assert match, f"unexpected artifact name: {item['name']}"
        shard = int(match.group(1))
        assert 0 <= shard < 64 and shard not in artifacts
        assert not item["expired"], f"artifact expired: {item['name']}"
        assert item["workflow_run"]["id"] == RUN_ID
        assert item["workflow_run"]["head_sha"] == RUN_HEAD
        artifacts[shard] = item
    assert len(artifacts) == payload["total_count"]
    return artifacts


def verify_receipt(artifact_dir, stem):
    output = (artifact_dir / "control_sage_verify.json" if stem == "control"
              else artifact_dir / "sage_verify.json")
    command([
        str(SAGE), "-python", str(VERIFIER), "--receipt",
        str(artifact_dir / f"{stem}.json"), "--runtime-info",
        str(RUNTIME), "--out", str(output)])


def ingest(shard, item, plan):
    name = item["name"]
    artifact_dir = ARCHIVE / name
    audit_dir = ARCHIVE / "audits"
    audit_path = audit_dir / f"shard-{shard}.json"
    if audit_path.exists():
        existing = json.loads(audit_path.read_text())
        assert existing["query_start"] == plan["query_starts"][shard]
        return existing["terminal_status"]
    if not artifact_dir.exists():
        with tempfile.TemporaryDirectory(prefix=f"q1091-shard-{shard}-",
                                         dir=ARCHIVE) as tmp:
            download_dir = Path(tmp) / "receipt"
            command(["gh", "run", "download", str(RUN_ID), "--repo",
                     "aburan28/cryptanalysis", "--name", name,
                     "--dir", str(download_dir)])
            assert (download_dir / "host.json").is_file()
            download_dir.rename(artifact_dir)
    host = json.loads((artifact_dir / "host.json").read_text())
    assert host["query_start"] == plan["query_starts"][shard]
    control = artifact_dir / "control.json"
    full = artifact_dir / "full.json"
    if control.is_file() and full.is_file():
        if not (artifact_dir / "sage_verify.json").exists():
            verify_receipt(artifact_dir, "full")
        if json.loads(control.read_text())["native_result"]["exact_hit_queries"]:
            if not (artifact_dir / "control_sage_verify.json").exists():
                verify_receipt(artifact_dir, "control")
    row = audit(artifact_dir, PLAN, RUNTIME, SNAPSHOT)
    assert row["query_start"] == plan["query_starts"][shard]
    audit_dir.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=audit_dir,
                                     prefix=f"shard-{shard}-", suffix=".tmp",
                                     delete=False) as handle:
        json.dump(row, handle, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    try:
        os.link(temp_path, audit_path)  # atomic create; never replace an audit
    finally:
        temp_path.unlink()
    return row["terminal_status"]


def scan(plan, max_new, continue_after_hit):
    artifacts = available_artifacts()
    if artifacts:
        runtime_is_current()
    results = []
    for shard, item in sorted(artifacts.items()):
        already = (ARCHIVE / "audits" / f"shard-{shard}.json").exists()
        if not already and sum(not row["already_audited"] for row in results) >= max_new:
            continue
        status = ingest(shard, item, plan)
        results.append({"shard": shard, "status": status,
                        "already_audited": already})
        print(json.dumps(results[-1]), flush=True)
        if status == "completed_verified_hit" and not continue_after_hit:
            print("Verified hit found; inspect its Sage replay and account "
                  "for all started jobs before stopping the wave.", flush=True)
            return True
    print(json.dumps({"available_artifacts": len(artifacts),
                      "audited_this_invocation": sum(
                          not row["already_audited"] for row in results)}),
          flush=True)
    return False


def workflow_terminal():
    row = json.loads(command(["gh", "run", "view", str(RUN_ID), "--repo",
                              "aburan28/cryptanalysis", "--json", "status"],
                             capture=True))
    return row["status"] == "completed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-new", type=int, default=64)
    parser.add_argument("--continue-after-hit", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=45)
    args = parser.parse_args()
    assert 0 <= args.max_new <= 64
    assert args.poll_seconds in range(1, 61)
    assert RUNTIME.is_file() and SNAPSHOT.is_file()
    plan = json.loads(PLAN.read_text())
    assert plan["candidate_id"].startswith("IC1N83Ckb1fb8000204")
    assert plan["run_id"] == (plan["candidate_id"] + "W" +
                              plan["workload_id"] + "R1")
    assert plan["isogeny"] == "none"
    terminal_observations = 0
    while True:
        try:
            if scan(plan, args.max_new, args.continue_after_hit):
                return
            if not args.watch:
                return
            terminal_observations = (terminal_observations + 1 if
                                     workflow_terminal() else 0)
            if terminal_observations >= 2:
                print("Q1091 workflow terminal; inspect the complete run "
                      "inventory and reconcile all attempts.", flush=True)
                return
        except subprocess.CalledProcessError as exc:
            if not args.watch:
                raise
            print(f"GitHub observation failed ({exc}); retrying", flush=True)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
