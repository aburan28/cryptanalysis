#!/usr/bin/env python3
"""Bounded native-XOR SAT measurement of the smaller exact N83 leaf circuit."""
import json
import os
import re
import resource
import signal
import subprocess
import time
from pathlib import Path

import build

HERE = Path(__file__).resolve().parent


def cpu_limit(soft, hard):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, hard))
    return apply


def verify_sat(label, output):
    p = build.read(HERE / "protocol.json")
    item = p["inputs"][label]
    old = build.parent.projected_sparse_leaf
    try:
        build.parent.projected_sparse_leaf = build.leaf.projected_sparse_leaf_double_reuse
        formula, raw, leaves, onb = build.parent.build(83, item["complement_x_coords"])
    finally:
        build.parent.projected_sparse_leaf = old
    for bits, value in zip(raw, item["pin_raw"]):
        build.parent.pin_bits(formula, bits, value)
    values = build.parent.parse_assignment(output, formula.variables)
    assert values is not None
    return build.parent.verify(formula, raw, leaves, onb,
                               item["complement_x_coords"], values)


def one(p, label):
    system = HERE / "formulas" / f"{label}_reuse.xcnf"
    receipt = next(r for r in build.read(HERE / "build_receipt.json")["rows"]
                   if r["label"] == label)
    assert build.sha(system) == receipt["reuse_formula_sha256"]
    solver = Path(p["solver_binary"])
    command = [str(solver), "--maxtime", str(p["cpu_soft_seconds_per_cell"]),
               "--maxconfl", str(p["max_conflicts"]), "--verb", "1",
               "--printsol", "1", str(system)]
    folder = HERE / "runs" / label
    folder.mkdir(parents=True, exist_ok=False)
    out, err = folder / "stdout.txt", folder / "stderr.txt"
    started = time.monotonic()
    reason = None
    with out.open("wb") as stdout, err.open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 preexec_fn=cpu_limit(
                                     p["cpu_soft_seconds_per_cell"],
                                     p["cpu_hard_seconds_per_cell"]))
        deadline, terminated = started + p["wall_seconds_per_cell"], None
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                break
            now = time.monotonic()
            if terminated is None and now >= deadline:
                reason = "WALL_CAP"
                child.terminate()
                terminated = now
            elif terminated is not None and now - terminated > 5:
                child.kill()
            time.sleep(0.05)
    output = out.read_text(errors="replace")
    check = (verify_sat(label, output) if "s SATISFIABLE" in output and
             reason is None else None)
    status_name = ("SAT_VERIFIED" if check else "WALL_CAP" if reason else
                   "CPU_CAP" if child.returncode in (-signal.SIGXCPU, -signal.SIGKILL)
                   else "INDETERMINATE" if "s INDETERMINATE" in output else
                   "UNSAT" if "s UNSATISFIABLE" in output else "PROCESS_FAILURE")
    matches = re.findall(r"^c\s*conflicts\s*:\s*([0-9]+)", output, re.M)
    row = {"label": label, "status": status_name, "command": command,
           "return_code": child.returncode, "termination_reason": reason,
           "formula_sha256": receipt["reuse_formula_sha256"],
           "solver_binary_sha256": p["solver_binary_sha256"],
           "exact_conflicts_if_reported": int(matches[-1]) if matches else None,
           "check": check,
           "wall_seconds_exploratory": time.monotonic() - started,
           "child_user_cpu_seconds": usage.ru_utime,
           "child_system_cpu_seconds": usage.ru_stime,
           "child_peak_rss_bytes_darwin": usage.ru_maxrss,
           "stdout_sha256": build.sha(out), "stderr_sha256": build.sha(err)}
    build.save(folder / "receipt.json", row)
    return row


def main():
    p = build.read(HERE / "protocol.json")
    assert not (HERE / "result.json").exists()
    assert build.sha(HERE / "build_receipt.json")
    assert build.sha(Path(p["solver_binary"])) == p["solver_binary_sha256"]
    partial = HERE / "result.partial.json"
    rows = build.read(partial)["rows"] if partial.exists() else []
    assert [r["label"] for r in rows] == p["measurement_order"][:len(rows)]
    for label in p["measurement_order"][len(rows):]:
        row = one(p, label)
        rows.append(row)
        build.save(partial, {"proposal_id": "Q1522", "rows": rows})
        print(label, row["status"], row["exact_conflicts_if_reported"], flush=True)
    build.save(HERE / "result.json", {
        "proposal_id": "Q1522", "candidate_id": None, "run_id": None,
        "curve_id": p["curve_id"], "isogeny": "none",
        "point_decomposition_stage_code": "PDP4sat",
        "protocol_sha256": build.sha(HERE / "protocol.json"),
        "source_sha256": build.sha(Path(__file__)), "rows": rows,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
