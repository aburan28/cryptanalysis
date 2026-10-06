#!/usr/bin/env python3
"""Paired, gated N53 weight-three/four-summand planted SAT control."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import platform
import random
import time

from circuit import Circuit, s3
from fc_hamming import require_exact_weight as fc_weight
from n53_group import COFACTOR, Curve, Field, LOW_TERMS, N, R, normal_basis
from unary_hamming import require_exact_weight as unary_weight
import run_n53_stage as stage

HERE = Path(__file__).resolve().parent
GEOMETRY = HERE / "runs/n53_weight3_geometry_v1/receipt.json"
SEED, WEIGHT, SUMMANDS = 53011, 3, 4


def geometry(field, curve, basis):
    raw_to_projected, x_masks, rejected = {}, {}, []
    for mask in itertools.combinations(range(N), WEIGHT):
        x = basis[mask[0]] ^ basis[mask[1]] ^ basis[mask[2]]
        points = curve.lift(x)
        if not points:
            rejected.append(mask)
            continue
        x_masks[x] = mask
        for point in points:
            image = curve.mul(point, COFACTOR)
            assert image is not None and curve.mul(image, R) is None
            raw_to_projected[point] = image
    expected = json.loads(GEOMETRY.read_text())
    assert len(raw_to_projected) == expected["geometric_points"] == 23426
    assert len(set(raw_to_projected.values())) == expected["actual_usable_projected_points"]
    assert len(rejected) == 11713
    assert stage.digest([list(p) for p in sorted(raw_to_projected)]) == expected["raw_set_sha256"]
    assert stage.digest([list(p) for p in sorted(raw_to_projected.values())]) == expected["projected_set_sha256"]
    return raw_to_projected, x_masks, rejected, expected


def fixture(curve, raw_to_projected):
    rng = random.Random(SEED)
    points = sorted(raw_to_projected)
    for attempt in range(1, 10001):
        picked = rng.sample(points, SUMMANDS)
        prefix = []
        total = None
        for point in picked:
            total = curve.add(total, point)
            prefix.append(total)
        if total is None or total[0] == 0:
            continue
        if any(point is None or point[0] == 0 for point in prefix[1:3]):
            continue
        return {"seed": SEED, "selection_attempt": attempt,
                "points": [list(p) for p in picked],
                "x": [p[0] for p in picked],
                "intermediate_x": [p[0] for p in prefix[1:3]],
                "target": list(total)}
    raise AssertionError("no nondegenerate planted fixture")


def build(circuit, basis, rejected, encoding, target_x):
    x_rows = [[circuit.variable() for _ in range(N)] for _ in range(SUMMANDS)]
    middle_rows = [[circuit.variable() for _ in range(N)] for _ in range(SUMMANDS - 2)]
    weight = fc_weight if encoding == "fc" else unary_weight
    for row in x_rows:
        weight(circuit, row, WEIGHT)
        circuit.clauses.extend(f"-{row[i]} -{row[j]} -{row[k]} 0"
                               for i, j, k in rejected)
    for row in middle_rows:
        circuit.clauses.append(" ".join(map(str, row)) + " 0")
    xs = [circuit.linear_element(row, basis) for row in x_rows]
    mids = [circuit.linear_element(row, [1 << j for j in range(N)])
            for row in middle_rows]
    for a, b, c in ((xs[0], xs[1], mids[0]),
                    (mids[0], xs[2], mids[1]),
                    (mids[1], xs[3], circuit.constant(target_x))):
        s3(circuit, a, b, c)
    return {"x_rows": x_rows, "middle_rows": middle_rows,
            "variables": circuit.next_var - 1,
            "cnf_clauses": len(circuit.clauses),
            "xor_rows": len(circuit.xors), "and_gates": circuit.and_count}


def pin_units(meta, fixture, x_masks):
    units = []
    for row, x in zip(meta["x_rows"], fixture["x"], strict=True):
        selected = set(x_masks[x])
        units.extend(var if i in selected else -var for i, var in enumerate(row))
    for row, value in zip(meta["middle_rows"], fixture["intermediate_x"], strict=True):
        units.extend(var if value >> i & 1 else -var for i, var in enumerate(row))
    assert len(units) == (SUMMANDS + SUMMANDS - 2) * N == 318
    assert len({abs(unit) for unit in units}) == len(units)
    return units


def pinned_formula(original, target, units):
    with original.open("rb") as source, target.open("wb") as out:
        header = source.readline().split()
        assert header[:2] == [b"p", b"cnf"]
        out.write(f"p cnf {int(header[2])} {int(header[3]) + len(units)}\n".encode())
        for block in iter(lambda: source.read(1 << 20), b""):
            out.write(block)
        out.write("".join(f"{unit} 0\n" for unit in units).encode())


def archive(path):
    raw = path.read_bytes()
    archived = path.with_suffix(path.suffix + ".gz")
    archived.write_bytes(gzip.compress(raw, mtime=0))
    path.unlink()
    return {"raw_sha256": hashlib.sha256(raw).hexdigest(),
            "archive_sha256": stage.file_hash(archived)}


def run_arm(out, circuit, meta, fixture_record, x_masks, raw_to_projected,
            curve, basis, encoding, workload, setup_ns, base_ns, build_ns):
    arm = out / encoding
    arm.mkdir()
    formula = arm / "system.xcnf"
    write_start = time.perf_counter_ns()
    circuit.write(formula)
    write_ns = time.perf_counter_ns() - write_start
    original_hash = stage.file_hash(formula)
    units = pin_units(meta, fixture_record, x_masks)
    pinned_dir = arm / "pinned"
    pinned_dir.mkdir()
    pinned_path = pinned_dir / "system.xcnf"
    pinned_formula(formula, pinned_path, units)
    pinned = stage.solve(pinned_path, pinned_dir, 5, 100000)
    pinned_model = stage.parse_model((pinned_dir / "solver.stdout.txt").read_text(errors="replace"))
    pinned_ok = pinned_model is not None and stage.verify_model(circuit, pinned_model)
    pinned_ok = pinned_ok and all(pinned_model.get(abs(unit)) == (unit > 0) for unit in units)
    assert pinned_ok, "the complete known-witness formula must pass before search"
    pinned_artifacts = {name: archive(pinned_dir / name)
                        for name in ("system.xcnf", "solver.stdout.txt", "solver.stderr.txt")}

    search_dir = arm / "search"
    search_dir.mkdir()
    search_path = search_dir / "system.xcnf"
    search_path.write_bytes(formula.read_bytes())
    search = stage.solve(search_path, search_dir, 10, 100000)
    model = stage.parse_model((search_dir / "solver.stdout.txt").read_text(errors="replace"))
    model_ok = model is not None and stage.verify_model(circuit, model)
    stage.TARGET = tuple(fixture_record["target"])
    lifted = stage.lift_model(curve, raw_to_projected, basis,
                              meta, model) if model_ok else None
    status = ("VERIFIED_DECOMPOSITION" if lifted and lifted["verified"] else
              "INVALID_MODEL_OR_GROUP_LIFT" if model is not None else
              search["guard"].upper() if search["guard"] else "INDETERMINATE")
    search_artifacts = {name: archive(search_dir / name)
                        for name in ("system.xcnf", "solver.stdout.txt", "solver.stderr.txt")}
    assert search_artifacts["system.xcnf"]["raw_sha256"] == original_hash
    formula.unlink()
    source_paths = [Path(__file__), HERE / "n53_group.py", HERE / "circuit.py",
                    HERE / "fc_hamming.py", HERE / "unary_hamming.py",
                    HERE / "run_n53_stage.py"]
    expected = json.loads(GEOMETRY.read_text())
    report = {"kind": "n53_weight3_s4_planted_hamming_pdp_stage",
              "status": status, "candidate_id": None, "run_id": None,
              "target_kind": "planted_control_not_natural_yield",
              "curve_id": expected["curve_id"], "encoding": encoding,
              "summands": SUMMANDS, "factor_base": {
                  "nominal_hamming_weight": WEIGHT,
                  "nominal_masks": expected["nominal_masks"],
                  "rational_x_count": expected["rational_x_count"],
                  "geometric_points": expected["geometric_points"],
                  "actual_usable_points": expected["actual_usable_projected_points"],
                  "effective_columns": expected["effective_signed_frobenius_columns"],
                  "projected_set_sha256": expected["projected_set_sha256"]},
              "fixture": fixture_record,
              "workload": workload, "workload_id": stage.digest(workload)[:12],
              "formula": {key: value for key, value in meta.items()
                          if key not in ("x_rows", "middle_rows")},
              "pinned_unit_count": len(units), "pinned_model_verified": pinned_ok,
              "pinned_attempt": pinned, "pinned_artifacts": pinned_artifacts,
              "search_attempt": search, "search_artifacts": search_artifacts,
              "model_xcnf_verified": model_ok, "group_lift": lifted,
              "phase_wall_ns": {"setup": setup_ns, "factor_base": base_ns,
                                "formula_build": build_ns, "xcnf_write": write_ns,
                                "pinned_solver": pinned["solver_wall_ns"],
                                "search_solver": search["solver_wall_ns"]},
              "limits": {"search_internal_seconds": 10,
                         "search_conflicts": 100000,
                         "search_external_watchdog_seconds": 30,
                         "solver_threads": 1,
                         "sampled_rss_guard_bytes": stage.MAX_RSS_BYTES},
              "solver_binary_sha256": stage.file_hash(stage.CMS),
              "sage_runtime_info_sha256": stage.file_hash(out / "sage_runtime_info.json"),
              "source_geometry_receipt_sha256": stage.file_hash(GEOMETRY),
              "source_sha256": {str(p.relative_to(stage.ROOT)): stage.file_hash(p)
                                for p in source_paths},
              "host": {"platform": platform.platform(),
                       "machine": platform.machine(), "python": platform.python_version()},
              "claim_boundary": "Known-witness N53 W3/S4 PDP control only. No natural relation, rank, DLP, or IC/rho speedup."}
    (arm / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    runtime = out / "sage_runtime_info.json"
    if not runtime.is_file():
        raise FileNotFoundError("save checked Sage runtime info before the measured control")
    assert set(out.iterdir()) == {runtime}
    setup_start = time.perf_counter_ns()
    field = Field()
    curve = Curve(field)
    _, basis = normal_basis(field)
    setup_ns = time.perf_counter_ns() - setup_start
    base_start = time.perf_counter_ns()
    raw_to_projected, x_masks, rejected, _ = geometry(field, curve, basis)
    base_ns = time.perf_counter_ns() - base_start
    planted = fixture(curve, raw_to_projected)
    exact_geometry = json.loads(GEOMETRY.read_text())
    workload = {"curve_id": exact_geometry["curve_id"],
                "subgroup_order": R, "target_group": "full_curve_group_planted_control",
                "target": planted["target"], "target_count": 1,
                "cold_target_count": 1, "warm_target_count": 0,
                "selection_seed": SEED,
                "input_law": "four distinct raw rational weight-three points sampled without replacement from sorted exact base"}
    results = []
    for encoding in ("fc", "unary"):
        circuit = Circuit(N, list(LOW_TERMS))
        build_start = time.perf_counter_ns()
        meta = build(circuit, basis, rejected, encoding, planted["target"][0])
        build_ns = time.perf_counter_ns() - build_start
        result = run_arm(out, circuit, meta, planted, x_masks, raw_to_projected,
                         curve, basis, encoding, workload, setup_ns, base_ns, build_ns)
        results.append({"encoding": encoding, "status": result["status"],
                        "formula": result["formula"],
                        "search_wall_ns": result["search_attempt"]["solver_wall_ns"]})
        print(json.dumps(results[-1], sort_keys=True), flush=True)
    (out / "summary.json").write_text(json.dumps({
        "kind": "n53_w3_s4_planted_paired_gate", "target": planted["target"],
        "workload_id": stage.digest(workload)[:12], "candidate_id": None,
        "results": results,
        "advance_to_ordinary_target": all(row["status"] == "VERIFIED_DECOMPOSITION"
                                          for row in results),
        "claim_boundary": "Planted control only; no ordinary-target or DLP claim."
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
