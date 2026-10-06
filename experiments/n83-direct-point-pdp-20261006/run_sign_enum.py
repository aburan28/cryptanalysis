#!/usr/bin/env python3
"""Enumerate five public-order lift-sign assignments on a frozen N83 circuit."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import psutil
import signal
import subprocess
import sys
import time

from bounded_direct_point import sampled_tree
from run_direct_point_branch import parse_model, replay


HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "sign_enum_protocol.json"
BASE_PROTOCOL = HERE / "protocol.json"
PUBLIC = HERE.parent / "hamming-ic-e2e-20260929/runs/n83_w34_sat_fixture_v1/public_input.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_xcnf(path: Path, model: dict[int, bool]) -> bool:
    """Check every CNF clause and native XOR row, including sign pins."""
    def literal_value(literal: int):
        value = model.get(abs(literal))
        return None if value is None else (value if literal > 0 else not value)

    with path.open() as source:
        header = source.readline().split()
        if len(header) != 4 or header[:2] != ["p", "cnf"]:
            return False
        variables, expected_rows = int(header[2]), int(header[3])
        if len(model) < variables:
            return False
        found_rows = 0
        for line in source:
            if not line.strip():
                continue
            words = line.split()
            if words[0] == "x":
                values = [literal_value(int(word)) for word in words[1:-1]]
                if None in values or sum(values) % 2 != 1:
                    return False
            else:
                values = [literal_value(int(word)) for word in words[:-1]]
                if not any(value is True for value in values):
                    return False
            found_rows += 1
        return found_rows == expected_rows


def make_variant(base_body: bytes, variables: int, rows: int,
                 sign_wires: list[int], branch: int, output: Path) -> None:
    pins = b"".join(f"{wire if branch & (1 << bit) else -wire} 0\n".encode()
                    for bit, wire in enumerate(sign_wires))
    with output.open("wb") as target:
        target.write(f"p cnf {variables} {rows + len(sign_wires)}\n".encode())
        target.write(base_body)
        if not base_body.endswith(b"\n"):
            target.write(b"\n")
        target.write(pins)


def run_solver(xcnf: Path, folder: Path, protocol: dict,
               global_start_ns: int) -> dict:
    argv = [str(SOLVER), "--verb=1", "--threads=1",
            f"--maxtime={protocol['solver_internal_seconds_per_branch']}",
            f"--maxconfl={protocol['solver_max_conflicts_per_branch']}",
            str(xcnf)]
    started = time.perf_counter_ns()
    peak_rss, sampled_cpu = 0, 0.0
    guard, guard_error = None, None
    stdout_path, stderr_path = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        child = subprocess.Popen(argv, stdout=stdout, stderr=stderr,
                                 start_new_session=True)
        root = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                rss, cpu = sampled_tree(root)
            except (psutil.AccessDenied, PermissionError) as error:
                guard = "process_inspection_error"
                guard_error = f"{type(error).__name__}: {error}"
                rss, cpu = 0, 0.0
            peak_rss = max(peak_rss, rss)
            sampled_cpu = max(sampled_cpu, cpu)
            if guard is None and peak_rss >= protocol["max_process_tree_rss_bytes"]:
                guard = "process_tree_rss_guard"
            if guard is None and (time.perf_counter_ns() - global_start_ns) / 1e9 >= \
                    protocol["external_total_wall_seconds"]:
                guard = "external_total_wall_guard"
            if guard is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        exit_code = child.wait()
    return {
        "argv": argv, "exit_code": exit_code,
        "guard": guard, "guard_error": guard_error,
        "solver_wall_ns": time.perf_counter_ns() - started,
        "sampled_process_tree_cpu_seconds": sampled_cpu,
        "sampled_process_tree_peak_rss_bytes": peak_rss,
        "stdout_sha256": sha(stdout_path),
        "stderr_sha256": sha(stderr_path),
    }


def main(out: Path, protocol_path: Path = PROTOCOL) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("sign-enumeration output is immutable")
    protocol_path = protocol_path.resolve()
    if protocol_path not in (PROTOCOL, HERE / "unpinned_sign_enum_protocol.json"):
        raise ValueError("unsupported frozen sign-enumeration protocol")
    protocol = json.loads(protocol_path.read_text())
    mode = protocol.get("source_mode", "pinned_planted")
    fiber_index = protocol.get("source_fiber_index", 0)
    source_names = {
        "pinned_planted": ("pinned_planted_f0_v2", "source_pinned_masks"),
        "unpinned_planted": ("unpinned_planted_f0_v1", "source_unpinned"),
    }
    source_name, source_key = source_names[mode]
    source = HERE / "runs" / source_name
    source_xcnf = source / "branch.xcnf"
    assert sha(BASE_PROTOCOL) == protocol["source_direct_point_protocol_sha256"]
    assert sha(source / "receipt.json") == protocol[f"{source_key}_receipt_sha256"]
    assert sha(source_xcnf) == protocol[f"{source_key}_xcnf_sha256"]
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    assert sha(SOLVER) == protocol["solver_binary_sha256"]
    public = json.loads(PUBLIC.read_text())
    source_receipt = json.loads((source / "receipt.json").read_text())
    assert source_receipt["mode"] == mode
    assert source_receipt["fiber_index"] == fiber_index
    assert source_receipt["status"] == "BOUNDED_UNKNOWN"
    sign_wires = protocol["sign_wires"]
    assert sign_wires == list(range(416, 421))
    with source_xcnf.open("rb") as stream:
        header = stream.readline().split()
        base_body = stream.read()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    variables, rows = int(header[2]), int(header[3])
    assert variables == source_receipt["circuit"]["variables"]
    assert rows == (source_receipt["circuit"]["cnf_clauses"] +
                    source_receipt["circuit"]["xor_rows"])
    out.mkdir(parents=True)
    save(out / "started.json", {
        "kind": protocol["kind"] + "_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(protocol_path),
        "source_xcnf_sha256": sha(source_xcnf),
        "source_receipt_sha256": sha(source / "receipt.json"),
        "runner_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(SOLVER),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started = time.perf_counter_ns()
    result = {
        "schema_version": 1,
        "kind": protocol["kind"],
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "status": "INCOMPLETE", "branch_count": 0,
        "branches": [], "verified_group_model": False,
        "online_target_wall_ns": None,
        "rho_online_wall_ns": None, "online_speedup": None,
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        fiber = public["planted"]["raw_target_fiber"][fiber_index]
        mask_rows = [[1 + 83 * slot + bit for bit in range(83)]
                     for slot in range(5)]
        conjugates = [int(value) for value in
                      public["normal_conjugates_polynomial_bits_decimal"]]
        for branch in range(32):
            if (time.perf_counter_ns() - started) / 1e9 >= \
                    protocol["external_total_wall_seconds"]:
                result["status"] = "GLOBAL_WALL_GUARD"
                break
            folder = out / f"branch_{branch:02d}"
            folder.mkdir()
            xcnf = out / "branch.xcnf"
            make_variant(base_body, variables, rows, sign_wires, branch, xcnf)
            if (time.perf_counter_ns() - started) / 1e9 >= \
                    protocol["external_total_wall_seconds"]:
                result["status"] = "GLOBAL_WALL_GUARD"
                break
            row = {
                "branch_index": branch,
                "xcnf_sha256": sha(xcnf),
                "xcnf_bytes": xcnf.stat().st_size,
            }
            row["solver"] = run_solver(xcnf, folder, protocol, started)
            output = (folder / "solver.stdout.txt").read_text(errors="replace")
            model = parse_model(output)
            if row["solver"]["guard"] is not None:
                row["status"] = "RESOURCE_GUARD"
            elif model is None:
                row["status"] = "UNSAT" if "s UNSATISFIABLE" in output else "BOUNDED_UNKNOWN"
            elif not verify_xcnf(xcnf, model):
                row["status"] = "MODEL_INVALID"
            else:
                check = replay(model, mask_rows, sign_wires, conjugates,
                               public, "planted", fiber)
                if check["verified"]:
                    save(folder / "private_model.json", check)
                    row["private_model_sha256_local_only"] = sha(folder / "private_model.json")
                    row["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE"
                    result["verified_group_model"] = True
                else:
                    row["status"] = "SAT_UNVERIFIED_GROUP"
                    row["group_check_error"] = check["reason"]
            save(folder / "receipt.json", row)
            result["branches"].append(row)
            result["branch_count"] += 1
            print(json.dumps({"branch": branch, "status": row["status"]},
                             sort_keys=True), flush=True)
            if row["status"] in ("SAT_GROUP_VERIFIED_PENDING_SAGE", "MODEL_INVALID",
                                 "SAT_UNVERIFIED_GROUP", "RESOURCE_GUARD"):
                result["status"] = row["status"]
                break
        else:
            result["status"] = "EXHAUSTED_ALL_SIGN_BRANCHES"
    except Exception as error:
        result["status"] = "ERROR"
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        result["attempt_wall_ns"] = time.perf_counter_ns() - started
        result["protocol_sha256"] = sha(protocol_path)
        result["started_sha256"] = sha(out / "started.json")
        save(out / "receipt.json", result)
        print(json.dumps({"status": result["status"],
                          "branches": result["branch_count"],
                          "wall_seconds": result["attempt_wall_ns"] / 1e9},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: run_sign_enum.py OUTPUT_DIRECTORY [FROZEN_PROTOCOL]")
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else PROTOCOL)
