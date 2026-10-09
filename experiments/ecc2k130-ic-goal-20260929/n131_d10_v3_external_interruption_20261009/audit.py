"""Write-once audit of the vanished d10/m15 v3 solver handle."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
RUN = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/m15_d10_static"
       / "single_target_runs"
       / "IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h91f3d222e01bW3c1992b7c92fR1")
QUERY = RUN / "precomputation/target_0001/model_01"
EXPECTED_PID = 60681
EXPECTED_CREATE_TIME = 1791568857.490002


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError("preserve first external-interruption audit")
    paths = {"started": RUN / "started.json",
             "progress": RUN / "precompute_progress.json",
             "query": QUERY / "query.xcnf",
             "stdout": QUERY / "cryptominisat.stdout.txt",
             "stderr": QUERY / "cryptominisat.stderr.txt",
             "pidfile": QUERY / "cryptominisat.pid"}
    if any(not path.is_file() for path in paths.values()):
        raise FileNotFoundError("frozen d10 v3 artifact missing")
    started = json.loads(paths["started"].read_text())
    progress = json.loads(paths["progress"].read_text())
    if (started["candidate_id"] !=
            "IC1N131Ckb1fb139384PDP15satRCdirectLAgaussTDdirectISO0h91f3d222e01b" or
            started["target_count"] != 1 or started["batch"] is not False or
            int(paths["pidfile"].read_text()) != EXPECTED_PID):
        raise ValueError("d10 v3 run identity changed")
    try:
        process = psutil.Process(EXPECTED_PID)
        identity_matched = abs(process.create_time() - EXPECTED_CREATE_TIME) < 0.05
        if identity_matched and process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
            raise RuntimeError("exact d10 solver still live; do not classify")
        pid_state = "reused_or_zombie"
    except psutil.NoSuchProcess:
        pid_state = "absent"
    lines = paths["stdout"].read_text(errors="replace").splitlines()
    statuses = [line for line in lines if line.startswith("s ")]
    models = [line for line in lines if line.startswith("v ")]
    last_restart = next((line for line in reversed(lines)
                         if line.startswith("c rst ")), None)
    if statuses or models or (RUN / "result.json").exists():
        raise ValueError("terminal/model artifact exists; inspect before classification")
    receipt = {
        "kind": "n131_d10_m15_v3_external_interruption_audit",
        "status": "PASS_EXACT_SOLVER_HANDLE_ABSENT_RAW_OUTPUT_RETAINED",
        "classification": "INTERRUPTED_PROCESS_ABSENT_RAW_OUTPUT_RETAINED",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": started["run_id"],
        "target_count": 1,
        "solver_pid": EXPECTED_PID,
        "solver_create_time_epoch": EXPECTED_CREATE_TIME,
        "solver_process_state": pid_state,
        "run_result_present": False,
        "surviving_rank": progress["rank"],
        "surviving_completed_attempts": len(progress["attempts"]),
        "solver_status_lines": statuses,
        "solver_model_line_count": len(models),
        "last_restart_line": last_restart,
        "stdout_bytes": paths["stdout"].stat().st_size,
        "stdout_last_modified_utc": datetime.fromtimestamp(
            paths["stdout"].stat().st_mtime, timezone.utc).isoformat(),
        "exact_stop_cause": None,
        "source_sha256": {**{key: sha(path) for key, path in paths.items()},
                          "auditor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "solver_process_state", "surviving_rank",
                       "surviving_completed_attempts")}))


if __name__ == "__main__":
    main()
