#!/usr/bin/env python3
"""Try public-order sign branches on the pinned indexed-factor N83 circuit."""

from __future__ import annotations

import json
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
DIRECT = HERE.parent / "n83-direct-point-pdp-20261006"
sys.path.insert(0, str(DIRECT))
from run_sign_enum import make_variant, run_solver, verify_xcnf  # noqa: E402
from run_indexed_branch import (DirectPointCircuit, decode_positions, factor,
                                parse_model, replay, sha, save, PUBLIC, SOLVER)  # noqa: E402


PROTOCOL = HERE / "sign_enum_protocol.json"
BASE_PROTOCOL = HERE / "protocol.json"
SOURCE = HERE / "runs/pinned_planted_f0_v1"
SOURCE_XCNF = SOURCE / "branch.xcnf"
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def group_replay(model: dict[int, bool], encoded: list[dict],
                 signs: list[int], conjugates: list[int], public: dict,
                 fiber: dict) -> dict:
    masks = [decode_positions(model, item) for item in encoded]
    fake = dict(model)
    first = max(model) + 1
    rows = []
    for slot, mask in enumerate(masks):
        row = list(range(first + 83 * slot, first + 83 * (slot + 1)))
        fake.update({wire: bit in mask for bit, wire in enumerate(row)})
        rows.append(row)
    return replay(fake, rows, signs, conjugates, public, "planted", fiber)


def main(out: Path) -> None:
    out = out.resolve()
    if out.exists():
        raise FileExistsError("sign-enumeration output is immutable")
    protocol = json.loads(PROTOCOL.read_text())
    assert sha(BASE_PROTOCOL) == protocol["source_base_protocol_sha256"]
    assert sha(SOURCE / "receipt.json") == protocol["source_pinned_receipt_sha256"]
    assert sha(SOURCE_XCNF) == protocol["source_pinned_xcnf_sha256"]
    assert sha(PUBLIC) == protocol["source_public_fixture_sha256"]
    assert sha(SOLVER) == protocol["solver_binary_sha256"]
    assert sha(DIRECT / "run_sign_enum.py") == protocol["source_sign_tools_sha256"]
    assert sha(DIRECT / "bounded_direct_point.py") == \
        protocol["source_sampling_watchdog_sha256"]
    source_receipt = json.loads((SOURCE / "receipt.json").read_text())
    assert source_receipt["status"] == "BOUNDED_UNKNOWN"
    assert source_receipt["mode"] == "pinned_planted"
    assert source_receipt["fiber_index"] == 0
    public = json.loads(PUBLIC.read_text())
    conjugates = [int(x) for x in public["normal_conjugates_polynomial_bits_decimal"]]
    builder = DirectPointCircuit(83, [0, 2, 4, 7])
    encoded = [factor(builder.circuit, conjugates) for _ in range(5)]
    signs = [builder.circuit.variable() for _ in range(5)]
    assert signs == protocol["sign_wires"]
    with SOURCE_XCNF.open("rb") as source:
        header = source.readline().split()
        base_body = source.read()
    assert header[:2] == [b"p", b"cnf"] and len(header) == 4
    variables, rows = int(header[2]), int(header[3])
    assert variables == source_receipt["circuit"]["variables"]
    assert rows == (source_receipt["circuit"]["cnf_clauses"] +
                    source_receipt["circuit"]["xor_rows"])
    out.mkdir(parents=True)
    with (out / "sage_runtime_info.json").open("wb") as runtime_info, \
         (out / "sage_runtime_info.stderr.txt").open("wb") as runtime_error:
        preflight = subprocess.run([str(SAGE), "--runtime-info"],
                                  stdout=runtime_info, stderr=runtime_error,
                                  check=False)
    if preflight.returncode:
        save(out / "preflight_failure.json", {
            "status": "SAGE_RUNTIME_PREFLIGHT_FAILURE",
            "exit_code": preflight.returncode,
            "stdout_sha256": sha(out / "sage_runtime_info.json"),
            "stderr_sha256": sha(out / "sage_runtime_info.stderr.txt"),
        })
        raise RuntimeError("checked Sage runtime preflight failed")
    save(out / "started.json", {
        "kind": "n83_indexed_factor_public_sign_start",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "protocol_sha256": sha(PROTOCOL),
        "source_xcnf_sha256": sha(SOURCE_XCNF),
        "source_receipt_sha256": sha(SOURCE / "receipt.json"),
        "runner_sha256": sha(Path(__file__)),
        "solver_binary_sha256": sha(SOLVER),
        "sage_runtime_info_sha256": sha(out / "sage_runtime_info.json"),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started = time.perf_counter_ns()
    result = {
        "schema_version": 1,
        "kind": "n83_indexed_factor_public_sign_enumeration",
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "status": "INCOMPLETE", "branch_count": 0,
        "branches": [], "verified_group_model": False,
        "online_target_wall_ns": None,
        "rho_online_wall_ns": None, "online_speedup": None,
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        fiber = public["planted"]["raw_target_fiber"][0]
        for branch in range(32):
            if (time.perf_counter_ns() - started) / 1e9 >= \
                    protocol["external_total_wall_seconds"]:
                result["status"] = "GLOBAL_WALL_GUARD"
                break
            folder = out / f"branch_{branch:02d}"
            folder.mkdir()
            xcnf = out / "branch.xcnf"
            make_variant(base_body, variables, rows, signs, branch, xcnf)
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
                checked = group_replay(model, encoded, signs, conjugates,
                                       public, fiber)
                if checked["verified"]:
                    save(folder / "private_model.json", checked)
                    row["private_model_sha256_local_only"] = \
                        sha(folder / "private_model.json")
                    row["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE"
                    result["verified_group_model"] = True
                else:
                    row["status"] = "SAT_UNVERIFIED_GROUP"
                    row["group_check_error"] = checked["reason"]
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
        result["protocol_sha256"] = sha(PROTOCOL)
        result["started_sha256"] = sha(out / "started.json")
        save(out / "receipt.json", result)
        print(json.dumps({"status": result["status"],
                          "branches": result["branch_count"],
                          "wall_seconds": result["attempt_wall_ns"] / 1e9},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_indexed_sign_enum.py OUTPUT_DIRECTORY")
    main(Path(sys.argv[1]))
