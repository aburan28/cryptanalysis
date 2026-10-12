#!/usr/bin/env python3
"""Regenerate one frozen N83 XCNF and give unpinned witness search a longer cap."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import resource
import signal
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "n83-costed-candidate-screen-20261005"
sys.path.insert(0, str(PRIOR))
from run_shifted_sat_branch import build, parse_model, replay, verify_model  # noqa: E402

PROTOCOL = HERE / "long_sat_protocol.json"
PANEL = PRIOR / "sat_panel.json"
OLD_PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sampled_tree(root: psutil.Process) -> tuple[int, float]:
    members = [psutil.Process(os.getpid())]
    try:
        members += [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    rss = 0
    cpu = 0.0
    for process in members:
        try:
            if process.is_running():
                rss += process.memory_info().rss
                clock = process.cpu_times()
                cpu += clock.user + clock.system
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return rss, cpu


def run_solver(xcnf: Path, out: Path, protocol: dict, attempt_start_ns: int) -> dict:
    command = [str(CMS), "--verb=1", "--threads=1",
               f"--maxtime={protocol['solver_internal_seconds']}",
               f"--maxconfl={protocol['solver_max_conflicts']}", str(xcnf)]
    started_ns = time.perf_counter_ns()
    peak_rss = 0
    sampled_cpu = 0.0
    guard = None
    with (out / "solver.stdout.txt").open("wb") as stdout, \
         (out / "solver.stderr.txt").open("wb") as stderr:
        child = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            rss, cpu = sampled_tree(root)
            peak_rss = max(peak_rss, rss)
            sampled_cpu = max(sampled_cpu, cpu)
            if peak_rss >= protocol["max_process_tree_rss_bytes"]:
                guard = "process_tree_rss_guard"
            elif (time.perf_counter_ns() - attempt_start_ns) / 1e9 >= \
                    protocol["external_wall_seconds"]:
                guard = "external_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
    totals = {}
    for name in ("restarts", "decisions", "propagations", "conflicts"):
        matches = re.findall(rf"(?m)^c {name}\s*:\s*(\d+)", stdout_text)
        totals[name] = int(matches[-1]) if matches else None
    return {
        "argv": command, "exit_code": exit_code, "guard": guard,
        "wall_ns": time.perf_counter_ns() - started_ns,
        "sampled_process_tree_peak_rss_bytes": peak_rss,
        "sampled_process_tree_cpu_seconds": sampled_cpu,
        "stdout_sha256": sha(out / "solver.stdout.txt"),
        "stderr_sha256": sha(out / "solver.stderr.txt"),
        "status_lines": [line for line in stdout_text.splitlines()
                         if line.startswith("s ")],
        "search_totals": totals,
    }


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("long SAT attempt output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    panel = json.loads(PANEL.read_text())
    row = next(row for row in panel["rows"]
               if row["name"] == protocol["source_panel_row"])
    assert row["candidate_id"] is None and row["target_kind"] == "planted"
    assert row["mode"] == "unpinned" and row["fiber_index"] == 0
    assert row["curve_id"] == protocol["curve_id"]
    assert row["xcnf"]["sha256"] == protocol["source_panel_xcnf_sha256"]
    assert row["public_fixture_sha256"] == protocol["source_panel_public_fixture_sha256"]
    assert sha(CMS) == protocol["solver_binary_sha256"]
    label = row["label"]
    geometry_path = PRIOR / "runs" / f"{label}_v1" / "geometry.json"
    fixture_path = PRIOR / "runs" / f"{label}_sat_fixture_v1" / "public_input.json"
    geometry = json.loads(geometry_path.read_text())
    fixture = json.loads(fixture_path.read_text())
    old = json.loads(OLD_PUBLIC.read_text())
    assert fixture["curve_id"] == geometry["curve_id"] == protocol["curve_id"]
    assert sha(fixture_path) == row["public_fixture_sha256"]
    assert fixture["planted"]["target_Q"] == row["target_Q"]
    assert fixture["planted"]["raw_target_fiber"][0] == row["raw_fiber"]
    branch_x = int(row["raw_fiber"]["x"])
    conjugates = [int(value) for value in old["normal_conjugates_polynomial_bits_decimal"]]
    assert len(conjugates) == 83
    out.mkdir(parents=True)
    source_paths = {
        "long_runner": Path(__file__),
        "original_runner": PRIOR / "run_shifted_sat_branch.py",
        "circuit": HERE.parent / "hamming-ic-e2e-20260929/circuit.py",
        "gf2n": HERE.parent / "pdp-scaling/gf2n.py",
    }
    save(out / "started.json", {
        "kind": "n83_shifted_s3_long_unpinned_sat_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "label": label, "target_kind": "planted", "fiber_index": 0,
        "target_Q": row["target_Q"], "raw_fiber": row["raw_fiber"],
        "protocol_sha256": sha(PROTOCOL), "source_panel_sha256": sha(PANEL),
        "geometry_sha256": sha(geometry_path),
        "public_fixture_sha256": sha(fixture_path),
        "source_sha256": {name: sha(path) for name, path in source_paths.items()},
        "solver_binary_sha256": sha(CMS),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    attempt_start_ns = time.perf_counter_ns()
    report = {
        "schema_version": 1, "kind": "n83_shifted_s3_long_unpinned_sat_attempt",
        "status": "INCOMPLETE", "candidate_id": None,
        "curve_id": protocol["curve_id"], "label": label,
        "target_kind": "planted", "fiber_index": 0,
        "target_Q": row["target_Q"], "branch_target_x_decimal": str(branch_x),
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        build_started = time.perf_counter_ns()
        circuit, rows = build(geometry, conjugates, branch_x, None, None)
        report["circuit_build_wall_ns"] = time.perf_counter_ns() - build_started
        report["circuit"] = {
            "variables": circuit.next_var - 1,
            "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
        }
        xcnf = out / "branch.xcnf"
        write_started = time.perf_counter_ns()
        circuit.write(xcnf)
        report["xcnf_write_wall_ns"] = time.perf_counter_ns() - write_started
        report["xcnf_bytes"] = xcnf.stat().st_size
        report["xcnf_sha256"] = sha(xcnf)
        assert report["xcnf_sha256"] == protocol["source_panel_xcnf_sha256"]
        parent_rss = psutil.Process(os.getpid()).memory_info().rss
        report["parent_rss_after_encoding_bytes"] = parent_rss
        if parent_rss >= protocol["max_process_tree_rss_bytes"]:
            report["status"] = "ENCODING_RSS_GUARD"
        elif (time.perf_counter_ns() - attempt_start_ns) / 1e9 >= \
                protocol["external_wall_seconds"]:
            report["status"] = "ENCODING_WALL_GUARD"
        else:
            report["solver"] = run_solver(xcnf, out, protocol, attempt_start_ns)
            solver_text = (out / "solver.stdout.txt").read_text(errors="replace")
            model = parse_model(solver_text)
            if model is None:
                report["status"] = ("UNSAT" if "s UNSATISFIABLE" in solver_text else
                                    "BOUNDED_UNKNOWN" if report["solver"]["guard"] else
                                    "SOLVER_UNKNOWN")
            elif not verify_model(circuit, model):
                report["status"] = "MODEL_INVALID"
            else:
                masks = [sum((1 << bit) for bit, variable in enumerate(mask_row)
                             if model[variable]) for mask_row in rows]
                x_codes = [0] * len(masks)
                for slot, mask in enumerate(masks):
                    for bit, basis_index in enumerate(geometry["slot_normal_basis_indices"][slot]):
                        if mask & (1 << bit):
                            x_codes[slot] ^= conjugates[basis_index]
                report["model"] = {
                    "mask_decimal": [str(mask) for mask in masks],
                    "factor_x_decimal": [str(value) for value in x_codes],
                    "cnf_xor_verified": True,
                }
                verify_started = time.perf_counter_ns()
                representatives = geometry_path.parent / "representatives.json.gz"
                report["group_check"] = replay(
                    x_codes, row["target_Q"],
                    [row["raw_fiber"]["x"], row["raw_fiber"]["y"]],
                    representatives)
                report["group_check_wall_ns"] = time.perf_counter_ns() - verify_started
                report["status"] = ("SAT_GROUP_VERIFIED_PENDING_SAGE" if
                                    report["group_check"]["verified"] else
                                    "SAT_UNVERIFIED_GROUP")
        report["self_peak_rss_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["self_peak_rss_unit"] = "bytes" if platform.system() == "Darwin" else "kilobytes"
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["attempt_wall_ns"] = time.perf_counter_ns() - attempt_start_ns
        report["started_sha256"] = sha(out / "started.json")
        report["protocol_sha256"] = sha(PROTOCOL)
        report["source_sha256"] = sha(Path(__file__))
        report["online_target_wall_ns"] = None
        report["rho_online_wall_ns"] = None
        report["online_speedup"] = None
        save(out / "receipt.json", report)
        print(json.dumps({"status": report["status"],
                          "attempt_wall_seconds": report["attempt_wall_ns"] / 1e9,
                          "guard": report.get("solver", {}).get("guard")},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_long_unpinned_sat.py OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
