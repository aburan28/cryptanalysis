#!/usr/bin/env python3
"""Audit the source-bound N83 XOR-matrix diagnostic receipts."""

import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / "experiments/n83-geometric-m5-fixedtarget16-20261012"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["proposal_id"] == "Q2026101251"
    assert protocol["candidate_id"] is None
    assert sha(PARENT / "protocol.json") == protocol["parent_protocol_sha256"]
    assert sha(PARENT / "width16_ordinary.json") == protocol[
        "parent_result_sha256"]
    assert sha(HERE / "sage_runtime_info.json") == protocol[
        "sage_runtime_info_sha256"]
    for relative, digest in protocol["source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    archive = ROOT / protocol["xcnf_gzip"]
    assert sha(archive) == protocol["xcnf_gzip_sha256"]
    with gzip.open(archive, "rb") as stream:
        raw = stream.read()
    assert len(raw) == protocol["xcnf_raw_bytes"]
    assert hashlib.sha256(raw).hexdigest() == protocol["xcnf_raw_sha256"]
    assert sha(Path(protocol["solver_path"])) == protocol["solver_sha256"]
    result = json.loads((HERE / "result.json").read_text())
    assert result["proposal_id"] == protocol["proposal_id"]
    assert result["curve_id"] == protocol["curve_id"]
    assert result["workload_id"] == protocol["workload_id"]
    assert result["protocol_sha256"] == sha(protocol_path)
    assert result["xcnf_raw_sha256"] == protocol["xcnf_raw_sha256"]
    assert result["timing_tier"] == protocol["timing_tier"]
    assert 1 <= len(result["arms"]) <= len(protocol["arms"])
    assert [row["name"] for row in result["arms"]] == [
        row["name"] for row in protocol["arms"][:len(result["arms"])]]
    verified = False
    summary = []
    for row, arm in zip(result["arms"], protocol["arms"]):
        assert row["extra_flags"] == arm["extra_flags"]
        assert row["command"] == [
            protocol["solver_path"], "--verb", "1", "--threads", "1",
            "--maxconfl", str(protocol["max_conflicts"]),
            *arm["extra_flags"], str(HERE / "input.xcnf")]
        stdout_path = HERE / row["stdout_file"]
        stderr_path = HERE / row["stderr_file"]
        assert sha(stdout_path) == row["stdout_sha256"]
        assert sha(stderr_path) == row["stderr_sha256"]
        stdout = stdout_path.read_text()
        conflicts = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                               flags=re.IGNORECASE)
        assert row["conflicts_reported"] == (int(conflicts[-1]) if conflicts
                                              else None)
        matrices = re.findall(r"Using\s+([0-9]+)\s+matrices", stdout)
        assert row["matrices_used_reported"] == [int(x) for x in matrices]
        restarts = [line.split() for line in stdout.splitlines()
                    if line.startswith("c rst")]
        last_restart_counter = restarts[-1][6] if restarts else None
        matrix_disable_messages = stdout.count(
            "TODO disable matrix, performing badly")
        assert row["wall_seconds"] <= protocol["wall_seconds_per_arm"] + 2
        assert row["observed_peak_solver_rss_bytes"] >= 0
        assert row["status"] in ("sat", "unsat", "external_timeout",
                                 "sampled_rss_cap_exceeded",
                                 "conflict_cap_indeterminate", "censored",
                                 "solver_failure")
        assert row["model_present"] == (row["replay"] is not None)
        if row["status"] == "sat":
            assert row["model_present"]
        if row["replay"] is not None and row["replay"]["status"] == (
                "verified_five_point_relation"):
            verified = True
        summary.append({"name": row["name"], "status": row["status"],
                        "conflicts": row["conflicts_reported"],
                        "last_restart_conflicts": last_restart_counter,
                        "matrices": row["matrices_used_reported"][-1:],
                        "matrix_disable_messages": matrix_disable_messages})
    assert result["status"] == ("verified_relation" if verified else
                                "bounded_diagnostic_complete")
    if len(result["arms"]) < len(protocol["arms"]):
        assert verified and protocol["stop_on_verified_relation"]
    assert not (HERE / "input.xcnf").exists()
    print(json.dumps({"status": "PASS", "arms": summary}, sort_keys=True))


if __name__ == "__main__":
    main()
