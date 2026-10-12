#!/usr/bin/env python3
"""Frozen CryptoMiniSat parameter sweep on an unpinned N53 S3 complement."""
import hashlib
import importlib.util
import json
import os
import re
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1513 = HERE.parent / "q20261012_fixed_pair_s3_handoff"
FORMULA = Q1513 / "n53_known_complement_unpinned.xcnf"
SOURCE = Q1513 / "run.py"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


parent = module("q1513_run", SOURCE)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def main():
    p = read(HERE / "protocol.json")
    assert sha(FORMULA) == p["formula_sha256"]
    assert sha(SOURCE) == p["q1513_run_source_sha256"]
    assert sha(Q1513 / "freeze.json") == p["q1513_freeze_sha256"]
    solver = Path(p["solver_binary"])
    assert sha(solver) == p["solver_binary_sha256"]
    assert not (HERE / "result.json").exists()
    parent_receipt = read(Q1513 / "n53_known_complement_unpinned.json")
    assert parent_receipt["formula_sha256"] == p["formula_sha256"]
    assert parent_receipt["pin_raw"] == parent_receipt["pin_projected"] == []
    complement_x = parent_receipt["complement_x_coords"]
    formula, raw, leaves, onb = parent.build(53, complement_x)
    rebuilt = HERE / "rebuilt.xcnf"
    formula.write(rebuilt)
    assert sha(rebuilt) == p["formula_sha256"]
    rebuilt.unlink()
    rows = []
    for setting in p["settings"]:
        folder = HERE / "runs" / setting["label"]
        folder.mkdir(parents=True, exist_ok=False)
        out, err = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
        command = [str(solver), "--maxtime", str(p["cpu_soft_seconds_per_cell"]),
                   "--maxconfl", str(p["max_conflicts"]),
                   "--verb", "1", "--printsol", "1", *setting["args"], str(FORMULA)]
        started, reason, usage = time.monotonic(), None, None
        with out.open("wb") as stdout, err.open("wb") as stderr:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                     preexec_fn=cpu_limit(
                                         p["cpu_soft_seconds_per_cell"],
                                         p["cpu_hard_seconds_per_cell"]))
            deadline, sent_at = started + p["wall_seconds_per_cell"], None
            while True:
                pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                if pid:
                    child.returncode = os.waitstatus_to_exitcode(status)
                    break
                now = time.monotonic()
                if sent_at is None and now >= deadline:
                    reason = "WALL_CAP"
                    child.terminate()
                    sent_at = now
                elif sent_at is not None and now - sent_at > 5:
                    child.kill()
                time.sleep(0.05)
        output = out.read_text(errors="replace")
        assignment = parent.parse_assignment(output, formula.variables) if (
            "s SATISFIABLE" in output and reason is None) else None
        check = parent.verify(formula, raw, leaves, onb, complement_x,
                              assignment) if assignment else None
        status_name = ("SAT_VERIFIED" if check else
                       "WALL_CAP" if reason == "WALL_CAP" else
                       "CPU_CAP" if child.returncode in
                       (-signal.SIGXCPU, -signal.SIGKILL) else
                       "INDETERMINATE" if "s INDETERMINATE" in output else
                       "UNSAT" if "s UNSATISFIABLE" in output else
                       "PROCESS_FAILURE")
        exact_conflicts = re.findall(r"^c\s*conflicts\s*:\s*([0-9]+)", output, re.M)
        row = {"setting": setting, "status": status_name,
               "return_code": child.returncode,
               "termination_reason": reason, "command": command,
               "formula_sha256": p["formula_sha256"],
               "solver_binary_sha256": p["solver_binary_sha256"],
               "exact_conflicts_if_reported": int(exact_conflicts[-1])
                   if exact_conflicts else None,
               "check": check,
               "wall_seconds_exploratory": time.monotonic() - started,
               "child_user_cpu_seconds": usage.ru_utime,
               "child_system_cpu_seconds": usage.ru_stime,
               "child_peak_rss_bytes_darwin": usage.ru_maxrss,
               "stdout_sha256": sha(out), "stderr_sha256": sha(err)}
        save(folder / "receipt.json", row)
        rows.append(row)
        save(HERE / "result.partial.json", {"proposal_id": "Q1519", "rows": rows})
        print(setting["label"], status_name, row["exact_conflicts_if_reported"],
              flush=True)
    save(HERE / "result.json", {"proposal_id": "Q1519", "candidate_id": None,
                                "run_id": None, "curve_id": p["curve_id"],
                                "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
                                "protocol_sha256": sha(HERE / "protocol.json"),
                                "source_sha256": sha(Path(__file__)),
                                "rows": rows, "complete_n53_decomposition_work_log2": None,
                                "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
