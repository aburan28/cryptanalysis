#!/usr/bin/env python3
"""Build and solve one frozen N83 direct-point regular-locus SAT branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

from direct_point_circuit import DirectPointCircuit
from gf2n import Curve, Point
from run_n83_w34_sat_branch import parse_model, verify_model
from weight34 import require_weight_three_or_four


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "hamming-ic-e2e-20260929"
PROTOCOL = HERE / "protocol.json"
PUBLIC = SOURCE / "runs/n83_w34_sat_fixture_v1/public_input.json"
REGENERATED = HERE / "runs/regenerated_fixture_v1"
PRIVATE = REGENERATED / "private_fixture.json"
REPS = SOURCE / "runs/n83_full_w4_geometry_v1/representatives.json"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, record) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def orbit_key(point: Point, field) -> tuple[int, int]:
    x, y = point.x, point.y
    keys = []
    for _ in range(field.n):
        keys.extend(((x, y), (x, x ^ y)))
        x, y = field.sqr(x), field.sqr(y)
    return min(keys)


def replay(model: dict[int, bool], mask_rows: list[list[int]], signs: list[int],
           conjugates: list[int], public: dict, kind: str, fiber: dict) -> dict:
    field = DirectPointCircuit(83, [0, 2, 4, 7]).field
    curve = Curve(field, 1)
    reps_record = json.loads(REPS.read_text())
    representatives = {tuple(row) for row in reps_record["representatives"]}
    masks = []
    factors = []
    for row, sign_wire in zip(mask_rows, signs):
        mask = [bit for bit, wire in enumerate(row) if model[wire]]
        if len(mask) not in (3, 4):
            return {"verified": False, "reason": "factor_weight", "weight": len(mask)}
        x = 0
        for bit in mask:
            x ^= conjugates[bit]
        if x == 0:
            return {"verified": False, "reason": "zero_factor_x"}
        w = x ^ field.sqr(field.inv(x))
        if field.trace(w):
            return {"verified": False, "reason": "nonrational_factor_x"}
        v = field.half_trace(w) ^ int(model[sign_wire])
        point = Point(x, field.mul(x, v))
        if not curve.on_curve(point):
            return {"verified": False, "reason": "factor_not_on_curve"}
        projected = curve.add(curve.add(point, point), curve.add(point, point))
        if projected.inf or orbit_key(projected, field) not in representatives:
            return {"verified": False, "reason": "factor_not_in_measured_base"}
        masks.append(mask)
        factors.append(point)
    prefix = factors[0]
    for factor in factors[1:]:
        if prefix.x == factor.x:
            return {"verified": False, "reason": "nonregular_prefix"}
        prefix = curve.add(prefix, factor)
        if prefix.inf:
            return {"verified": False, "reason": "identity_prefix"}
    raw = [str(prefix.x), str(prefix.y)]
    if raw != [fiber["x"], fiber["y"]]:
        return {"verified": False, "reason": "raw_fiber_mismatch"}
    projected = curve.add(curve.add(prefix, prefix), curve.add(prefix, prefix))
    if [str(projected.x), str(projected.y)] != public[kind]["target_Q"]:
        return {"verified": False, "reason": "subgroup_target_mismatch"}
    return {
        "verified": True,
        "masks": masks,
        "signs": [int(model[wire]) for wire in signs],
        "raw_factor_points": [[str(point.x), str(point.y)] for point in factors],
        "raw_sum": raw,
        "projected_sum": public[kind]["target_Q"],
        "measured_base_membership": True,
    }


def main(mode: str, fiber_index: int, out: Path) -> None:
    out = out.resolve()
    if not out.is_dir() or (out / "started.json").exists():
        raise FileExistsError("outer runner must create a fresh output directory")
    protocol = json.loads(PROTOCOL.read_text())
    public = json.loads(PUBLIC.read_text())
    regenerated = json.loads((REGENERATED / "public_input.json").read_text())
    assert sha(PUBLIC) == sha(REGENERATED / "public_input.json") == \
        protocol["source_public_fixture_sha256"]
    assert public == regenerated
    assert public["curve_id"] == protocol["curve_id"]
    assert sha(SOURCE / "n83_w34_sat_protocol.json") == \
        protocol["source_public_fixture_protocol_sha256"]
    assert sha(REPS) == protocol["full_w34_representatives_sha256"]
    assert sha(SOLVER) == protocol["solver_binary_sha256"]
    assert mode in ("pinned_planted", "unpinned_planted", "ordinary")
    kind = "ordinary" if mode == "ordinary" else "planted"
    assert fiber_index in range(4)
    fiber = public[kind]["raw_target_fiber"][fiber_index]
    private = None
    if mode == "pinned_planted":
        assert sha(PRIVATE) == protocol["regenerated_private_fixture_sha256_local_only"]
        private = json.loads(PRIVATE.read_text())
        assert private["public_input_sha256"] == sha(PUBLIC)
        assert [fiber["x"], fiber["y"]] == private["raw_sum"]
    sources = {
        "runner": Path(__file__),
        "direct_point_circuit": HERE / "direct_point_circuit.py",
        "generic_circuit": SOURCE / "circuit.py",
        "weight34": SOURCE / "weight34.py",
        "gf2n": HERE.parent / "pdp-scaling/gf2n.py",
        "model_verifier": SOURCE / "run_n83_w34_sat_branch.py",
    }
    save(out / "started.json", {
        "kind": "n83_w34_direct_point_branch_start",
        "mode": mode, "fiber_index": fiber_index,
        "candidate_id": None, "curve_id": protocol["curve_id"],
        "public_fixture_sha256": sha(PUBLIC),
        "private_fixture_sha256_local_only": sha(PRIVATE) if private is not None else None,
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": {name: sha(path) for name, path in sources.items()},
        "solver_binary_sha256": sha(SOLVER),
        "architecture": platform.machine(), "os": platform.platform(),
    })
    started = time.perf_counter_ns()
    report = {
        "schema_version": 1,
        "kind": "n83_w34_direct_point_branch",
        "status": "INCOMPLETE", "candidate_id": None,
        "curve_id": protocol["curve_id"], "mode": mode,
        "fiber_index": fiber_index,
        "target_kind": kind,
        "target_Q": public[kind]["target_Q"],
        "regular_locus_only": True,
        "claim_boundary": protocol["claim_boundary"],
    }
    try:
        begin = time.perf_counter_ns()
        builder = DirectPointCircuit(83, [0, 2, 4, 7])
        circuit = builder.circuit
        mask_rows = [[circuit.variable() for _ in range(83)] for _ in range(5)]
        signs = [circuit.variable() for _ in range(5)]
        for row in mask_rows:
            require_weight_three_or_four(circuit, row)
        conjugates = [int(value) for value in
                      public["normal_conjugates_polynomial_bits_decimal"]]
        factor_x = [circuit.linear_element(row, conjugates) for row in mask_rows]
        builder.require_sum(factor_x, signs, int(fiber["x"]), int(fiber["y"]))
        if mode == "pinned_planted":
            assert private is not None
            for row, selected in zip(mask_rows, private["selected"]):
                mask = set(selected["mask"])
                for bit, wire in enumerate(row):
                    circuit.clauses.append(f"{wire if bit in mask else -wire} 0")
        report["circuit_build_wall_ns"] = time.perf_counter_ns() - begin
        report["circuit"] = {
            "variables": circuit.next_var - 1,
            "and_gates": circuit.and_count,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors),
        }
        begin = time.perf_counter_ns()
        xcnf = out / "branch.xcnf"
        circuit.write(xcnf)
        report["xcnf_write_wall_ns"] = time.perf_counter_ns() - begin
        report["xcnf_sha256"] = sha(xcnf)
        report["xcnf_bytes"] = xcnf.stat().st_size
        argv = [str(SOLVER), "--verb=1", "--threads=1",
                f"--maxtime={protocol['solver_internal_seconds']}",
                f"--maxconfl={protocol['solver_max_conflicts']}", str(xcnf)]
        begin = time.perf_counter_ns()
        with (out / "solver.stdout.txt").open("wb") as stdout, \
             (out / "solver.stderr.txt").open("wb") as stderr:
            child = subprocess.run(argv, stdout=stdout, stderr=stderr,
                                   check=False)
        report["solver_wall_ns"] = time.perf_counter_ns() - begin
        report["solver"] = {
            "argv": argv, "exit_code": child.returncode,
            "stdout_sha256": sha(out / "solver.stdout.txt"),
            "stderr_sha256": sha(out / "solver.stderr.txt"),
        }
        stdout_text = (out / "solver.stdout.txt").read_text(errors="replace")
        model = parse_model(stdout_text)
        if model is None:
            report["status"] = "UNSAT" if "s UNSATISFIABLE" in stdout_text else "BOUNDED_UNKNOWN"
        elif not verify_model(circuit, model):
            report["status"] = "MODEL_INVALID"
        else:
            checked = replay(model, mask_rows, signs, conjugates, public, kind, fiber)
            if checked["verified"]:
                save(out / "private_model.json", checked)
                report["private_model_sha256_local_only"] = sha(out / "private_model.json")
                report["group_verified"] = True
                report["cnf_xor_verified"] = True
                report["status"] = "SAT_GROUP_VERIFIED_PENDING_SAGE"
            else:
                report["status"] = "SAT_UNVERIFIED_GROUP"
                report["group_check_error"] = checked["reason"]
    except Exception as error:
        report["status"] = "ERROR"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["attempt_wall_ns"] = time.perf_counter_ns() - started
        report["self_peak_rss_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["self_peak_rss_unit"] = "bytes" if platform.system() == "Darwin" else "kilobytes"
        report["started_sha256"] = sha(out / "started.json")
        report["protocol_sha256"] = sha(PROTOCOL)
        report["online_target_wall_ns"] = None
        report["rho_online_wall_ns"] = None
        report["online_speedup"] = None
        save(out / "receipt.json", report)
        print(json.dumps({"status": report["status"],
                          "attempt_wall_seconds": report["attempt_wall_ns"] / 1e9},
                         sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pinned_planted", "unpinned_planted", "ordinary"))
    parser.add_argument("fiber_index", type=int)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.mode, args.fiber_index, args.out)
