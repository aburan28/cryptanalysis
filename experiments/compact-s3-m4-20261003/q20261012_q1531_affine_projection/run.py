#!/usr/bin/env python3
"""Run frozen affine-projected ANF cells and lift models for exact replay."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1528 = HERE.parent / "q20261012_q1528_gate_elimination"
sys.path.insert(0, str(Q1528))
import project  # noqa: E402

spec = importlib.util.spec_from_file_location("q1528_run", Q1528 / "run.py")
q28 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q28)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def cpu_limit() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 35))


def main(label: str) -> None:
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert label in protocol["panel_order"]
    assert sha(Path(protocol["solver_path"])) == protocol["solver_sha256"]
    assert sha(HERE / "project.py") == protocol["converter_sha256"]
    assert sha(HERE / "run.py") == protocol["runner_sha256"]
    frozen = protocol["inputs"][label]
    folder = HERE / "formulas"
    for name, key in ((f"{label}.anf", "anf_sha256"),
                      (f"{label}.anf.gz", "gzip_sha256"),
                      (f"{label}.basis.json", "basis_sha256")):
        assert sha(folder / name) == frozen[key]
    assert sha(Q1528 / "formulas" / f"{label}.anf.gz") == frozen["source_gzip_sha256"]
    destination = HERE / "runs" / label
    destination.mkdir(parents=True, exist_ok=False)
    command = [protocol["solver_path"], *protocol["solver_options"],
               str(folder / f"{label}.anf")]
    out, err = destination / "stdout.txt", destination / "stderr.txt"
    started = time.monotonic()
    reason = None
    with out.open("wb") as stdout, err.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 preexec_fn=cpu_limit)
        terminated = None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if terminated is None and now - started >= protocol["wall_seconds"]:
                reason = "WALL_CAP"
                child.terminate()
                terminated = now
            elif terminated is not None and now - terminated >= 5:
                child.kill()
            time.sleep(0.05)
    stdout = out.read_text(errors="replace")
    bitstrings = [line[2:] for line in stdout.splitlines()
                  if line.startswith("s ") and set(line[2:]) <= {"0", "1"}]
    verified, verification_error = None, None
    if "s SATISFIABLE" in stdout:
        try:
            assert len(bitstrings) == 1
            basis_record = json.loads((folder / f"{label}.basis.json").read_text())
            lifted = project.lift_model(bitstrings[0], basis_record["live"],
                                        basis_record["basis"], frozen["original_variables"])
            n, rows, _, _ = project.load(label)
            assert len(lifted) == n and project.evaluate(rows, lifted)
            projected_n, projected_rows, _, _ = project.parse_data(
                (folder / f"{label}.anf").read_bytes())
            assert projected_n == len(bitstrings[0])
            assert project.evaluate(projected_rows, bitstrings[0])
            verified = q28.verify_sat(label, "s " + lifted + "\n")
        except Exception as exc:
            verification_error = repr(exc)
    status = ("SAT_VERIFIED" if verified else
              "UNVERIFIED_MODEL" if "s SATISFIABLE" in stdout else
              "WALL_CAP" if reason else
              "INDETERMINATE" if "s INDETERMINATE" in stdout else
              "UNSAT" if "s UNSATISFIABLE" in stdout else
              "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL) else
              "PROCESS_FAILURE")
    conflicts = re.findall(r"^c conflicts\s*:\s*([0-9]+)", stdout, re.I | re.M)
    receipt = {
        "proposal_id": "Q1531", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_ids"]["n53" if label.startswith("n53") else "n83"],
        "isogeny": "none", "stage_code": "PDP4sat",
        "label": label, "status": status, "command": command,
        "return_code": child.returncode, "termination_reason": reason,
        "wall_seconds_exploratory": time.monotonic() - started,
        "child_user_cpu_seconds": usage.ru_utime,
        "child_system_cpu_seconds": usage.ru_stime,
        "child_peak_rss_bytes_darwin": usage.ru_maxrss,
        "reported_conflicts_last": int(conflicts[-1]) if conflicts else None,
        "stdout_sha256": sha(out), "stderr_sha256": sha(err),
        "verification": verified, "verification_error": verification_error,
        "ordinary_verified_relations": int(bool(verified) and "ordinary" in label or
                                           bool(verified) and label in ("n83_selected", "n83_holdout")),
        "complete_n131_solve_work_log2": None,
    }
    save(destination / "receipt.json", receipt)
    print(label, status, receipt["reported_conflicts_last"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    main(parser.parse_args().label)
