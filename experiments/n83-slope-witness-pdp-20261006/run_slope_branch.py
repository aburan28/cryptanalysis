#!/usr/bin/env python3
"""Build and solve one frozen N83 indexed-factor slope-witness SAT branch."""

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

HERE = Path(__file__).resolve().parent
DIRECT = HERE.parent / "n83-direct-point-pdp-20261006"
INDEXED = HERE.parent / "n83-indexed-factor-pdp-20261006"
sys.path.insert(0, str(DIRECT))
sys.path.insert(0, str(INDEXED))
from slope_witness_circuit import SlopeWitnessCircuit
from gf2n import Curve, Point
from run_n83_w34_sat_branch import parse_model, verify_model
from indexed_factor import decode_positions, factor, pin_positions


SOURCE = HERE.parent / "hamming-ic-e2e-20260929"
PROTOCOL = HERE / "protocol.json"
PUBLIC = SOURCE / "runs/n83_w34_sat_fixture_v1/public_input.json"
REGENERATED = HERE.parent / "n83-direct-point-pdp-20261006/runs/regenerated_fixture_v1"
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


def decode(wires: list[int], model: dict[int, bool]) -> int:
    return sum(1 << bit for bit, wire in enumerate(wires)
               if wire == -1 or (wire != 0 and model[wire]))


def replay(model: dict[int, bool], encoded: list[dict], witness: dict,
           conjugates: list[int], public: dict, kind: str, fiber: dict) -> dict:
    field = SlopeWitnessCircuit(83, [0, 2, 4, 7]).field
    curve = Curve(field, 1)
    reps_record = json.loads(REPS.read_text())
    representatives = {tuple(row) for row in reps_record["representatives"]}
    masks = []
    factors = []
    for item, (x_row, y_row) in zip(encoded, witness["factors"]):
        mask = decode_positions(model, item)
        x = 0
        for bit in mask:
            x ^= conjugates[bit]
        if x == 0 or decode(x_row, model) != x:
            return {"verified": False, "reason": "invalid_factor_x"}
        point = Point(x, decode(y_row, model))
        if not curve.on_curve(point):
            return {"verified": False, "reason": "factor_not_on_curve"}
        projected = curve.add(curve.add(point, point), curve.add(point, point))
        if projected.inf or orbit_key(projected, field) not in representatives:
            return {"verified": False, "reason": "factor_not_in_measured_base"}
        masks.append(mask)
        factors.append(point)
    prefix = factors[0]
    for factor, slope_wires, prefix_wires in zip(
            factors[1:], witness["slopes"], witness["prefixes_after_addition"]):
        if prefix.x == factor.x:
            return {"verified": False, "reason": "nonregular_prefix"}
        denominator = prefix.x ^ factor.x
        slope = field.mul(prefix.y ^ factor.y, field.inv(denominator))
        if decode(slope_wires, model) != slope:
            return {"verified": False, "reason": "slope_mismatch"}
        prefix = curve.add(prefix, factor)
        if prefix.inf or [decode(row, model) for row in prefix_wires] != \
                [prefix.x, prefix.y]:
            return {"verified": False, "reason": "prefix_mismatch"}
    raw = [str(prefix.x), str(prefix.y)]
    if raw != [fiber["x"], fiber["y"]]:
        return {"verified": False, "reason": "raw_fiber_mismatch"}
    projected = curve.add(curve.add(prefix, prefix), curve.add(prefix, prefix))
    if [str(projected.x), str(projected.y)] != public[kind]["target_Q"]:
        return {"verified": False, "reason": "subgroup_target_mismatch"}
    return {
        "verified": True,
        "masks": masks,
        "raw_factor_points": [[str(point.x), str(point.y)] for point in factors],
        "raw_sum": raw,
        "projected_sum": public[kind]["target_Q"],
        "measured_base_membership": True,
        "all_slopes_checked": True,
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
    assert sha(INDEXED / "indexed_factor.py") == protocol["source_indexed_factor_sha256"]
    assert sha(HERE / "slope_witness_circuit.py") == \
        protocol["source_slope_witness_circuit_sha256"]
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
        "indexed_factor": INDEXED / "indexed_factor.py",
        "slope_witness_circuit": HERE / "slope_witness_circuit.py",
        "generic_circuit": SOURCE / "circuit.py",
        "gf2n": HERE.parent / "pdp-scaling/gf2n.py",
        "model_verifier": SOURCE / "run_n83_w34_sat_branch.py",
    }
    save(out / "started.json", {
        "kind": "n83_w34_slope_witness_branch_start",
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
        "kind": "n83_w34_slope_witness_branch",
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
        builder = SlopeWitnessCircuit(83, [0, 2, 4, 7])
        circuit = builder.circuit
        conjugates = [int(value) for value in
                      public["normal_conjugates_polynomial_bits_decimal"]]
        encoded = [factor(circuit, conjugates) for _ in range(5)]
        factor_x = [item["x"] for item in encoded]
        witness = builder.require_sum(factor_x, int(fiber["x"]), int(fiber["y"]))
        if mode == "pinned_planted":
            assert private is not None
            for item, selected in zip(encoded, private["selected"]):
                pin_positions(circuit, item, selected["mask"])
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
            checked = replay(model, encoded, witness, conjugates,
                             public, kind, fiber)
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
