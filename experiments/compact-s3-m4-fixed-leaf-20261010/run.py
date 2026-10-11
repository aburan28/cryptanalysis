#!/usr/bin/env python3
"""Frozen Q1423 fixed-leaf N53/N83 controls and ordinary query probes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from chain_s3_base_orbit import decode_base_choice  # noqa: E402
from chain_s3_multitarget import decode_choice  # noqa: E402
from orbit_key import OrbitKey  # noqa: E402
from q1325_inputs import read_inputs as read_n83  # noqa: E402
from run_base_orbit_probe import (point_choice, read_inputs as read_n53,
                                  witness_points)  # noqa: E402
from run_probe import curves, field, parse_model  # noqa: E402
from run_q1404_raw_preimage_w5 import (fixture_target,
                                        preimage_coset)  # noqa: E402
from cofactor_preimages import kernel_of_cofactor  # noqa: E402
from fixed_leaf import arithmetic, build_exact, build_raw  # noqa: E402

SOLVER = Path(shutil.which("cryptominisat5") or "/opt/homebrew/bin/cryptominisat5")
OLD_SOURCES = (
    "chain_s3.py", "chain_s3_base_orbit.py", "chain_s3_factored.py",
    "chain_s3_ordered.py", "chain_s3_orbit.py", "chain_s3_multitarget.py",
    "run_base_orbit_probe.py", "run_probe.py", "q1325_inputs.py",
    "run_q1325_full_weight5_probe.py", "run_q1404_raw_preimage_w5.py",
    "cofactor_preimages.py",
)
ROOT_SOURCES = (
    "ecc2k130/codegen/field.py", "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
)
INPUTS = (
    "bases/n53_weight3_orbits.json.gz", "runs/n53_ordinary_frozen.json",
    "runs/n53_ordinary_matched_pair_table.json", "protocol.json",
    "bases/n83_weight5_full_orbits.json",
    "bases/n83_weight5_full_point_orbits.bin",
    "runs/n83_ordinary_frozen.json", "runs/n83_q1325_planted_locked.json",
)
EXPECTED = {
    53: ("EC1N53Ckb1hf77aab617904", "74f2979b3e68", 24062, 227,
         "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5"),
    83: ("EC1N83Ckb1h876c2921cb64", "bab50a1e5f66", 30977592, 186612,
         "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8"),
}


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze():
    assert SOLVER.is_file(), SOLVER
    record = {
        "schema": "q1423-fixed-leaf-freeze-v1", "proposal_id": "Q1423",
        "candidate_id": None, "isogeny": "none",
        "protocol_sha256": sha_file(HERE / "PROTOCOL.md"),
        "builder_sha256": sha_file(HERE / "fixed_leaf.py"),
        "runner_sha256": sha_file(__file__),
        "solver_binary": str(SOLVER.resolve()),
        "solver_binary_sha256": sha_file(SOLVER),
        "old_source_sha256": {name: sha_file(OLD / name) for name in OLD_SOURCES},
        "root_source_sha256": {name: sha_file(ROOT / name) for name in ROOT_SOURCES},
        "input_sha256": {name: sha_file(OLD / name) for name in INPUTS},
        "controls": {"solver_seconds": 30, "external_seconds": 40,
                     "max_conflicts": 1000000, "rss_mib": 1536},
        "search": {"solver_seconds": 120, "external_seconds": 135,
                   "max_conflicts": 1000000, "rss_mib": 1536},
        "selection_seed": 1423,
        "cases": {str(n): {"curve_id": values[0], "ordinary_workload_id": values[1],
                           "actual_B": values[2], "folded_K": values[3],
                           "base_digest": values[4]}
                  for n, values in EXPECTED.items()},
    }
    path = HERE / "freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(sha_file(path))


def check_freeze():
    record = json.loads((HERE / "freeze.json").read_text())
    assert record["proposal_id"] == "Q1423" and record["candidate_id"] is None
    assert record["protocol_sha256"] == sha_file(HERE / "PROTOCOL.md")
    assert record["builder_sha256"] == sha_file(HERE / "fixed_leaf.py")
    assert record["runner_sha256"] == sha_file(__file__)
    assert record["solver_binary_sha256"] == sha_file(SOLVER)
    assert all(sha_file(OLD / name) == value
               for name, value in record["old_source_sha256"].items())
    assert all(sha_file(ROOT / name) == value
               for name, value in record["root_source_sha256"].items())
    assert all(sha_file(OLD / name) == value
               for name, value in record["input_sha256"].items())
    return record


def load_case(n, mode):
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    expected = EXPECTED[n]
    if n == 53:
        _, baseline, _, base, keys = read_n53(n, "ordinary")
        assert (baseline["curve_id"], baseline["workload_id"],
                baseline["factor_base_actual_B"],
                baseline["factor_base_folded_columns"],
                baseline["factor_base_enumerated_set_sha256"]) == expected
        public = tuple(map(int, baseline["public_subgroup_target"]))
        witness = None
        if mode in ("locked", "control_unpinned"):
            _, points = witness_points(n, "ordinary", onb, curve, baseline, 428)
            index = {key: i for i, key in enumerate(keys)}
            pairs = sorted((point_choice(onb, keys, index, point), point)
                           for point in points)
            witness = {"points": [point for _, point in pairs],
                       "choices": [choice for choice, _ in pairs]}
        order = int(base["curve"]["subgroup_order"])
    else:
        _, base, _, keys, _, baseline = read_n83()
        assert (base["curve"]["curve_id"], baseline["workload_id"],
                base["factor_base"]["actual_usable_points_B_before_folding"],
                base["factor_base"]["signed_frobenius_columns"],
                base["factor_base"]["enumerated_set_sha256"]) == expected
        order = int(base["curve"]["subgroup_order"])
        witness = None
        if mode in ("locked", "control_unpinned"):
            raw_x, raw_points, _, _, public = fixture_target(
                onb, curve, set(keys), 830525)
            witness = {"raw_x": raw_x, "raw_points": raw_points,
                       "points": [curve.mul(point, 4) for point in raw_points]}
            assert all(point is not None for point in witness["points"])
        else:
            public = tuple(map(int, baseline["public_subgroup_target"]))
    assert curve.onCurve(public) and curve.mul(public, order) is None
    return onb, curve, public, order, keys, witness


def select_fixed(n, onb, curve, public, keys, mode, witness, seed):
    if witness is not None:
        return witness["points"][3], None, 0, 0
    pool = {"pool1": 1, "pool64": 64}[mode]
    orbit = OrbitKey(onb) if n == 83 else None
    best = None
    for index in range(pool):
        material = (f"Q1423|{n}|{seed}|{public[0]}|{public[1]}|{index}").encode()
        raw = int.from_bytes(hashlib.sha256(material).digest(), "little")
        key_index = raw % len(keys)
        shift = raw // len(keys) % n
        sign = -1 if raw >> 255 else 1
        if n == 53:
            rep = curve.pointFromX(onb.fromCoords(keys[key_index]))
            assert rep is not None
        else:
            rep = orbit.point_from_key(keys[key_index])
        point = curve.frob(rep, shift)
        if sign < 0:
            point = curve.neg(point)
        remainder = curve.add(public, curve.neg(point))
        if remainder is None:
            continue
        x = onb.toCoords(remainder[0])
        ranking = (x.bit_count(), x, index)
        if best is None or ranking < best[0]:
            best = (ranking, point, remainder, key_index, shift, sign)
    assert best is not None
    _, point, _, _, _, _ = best
    return point, {"selected_index": best[0][2], "key_index": best[3],
                   "shift": best[4], "sign": best[5],
                   "remainder_x_weight": best[0][0]}, pool, pool


def pin(formula, bits, value):
    formula.clauses.extend(([bit if value >> i & 1 else -bit]
                            for i, bit in enumerate(bits)))


def build(n, onb, curve, order, keys, target, witness, mode, preimages):
    math = arithmetic(onb)
    if n == 53:
        result = build_exact(n, keys, onb.toCoords(target[0]), math)
        formula, leaves, mid, choices, _ = result
        if mode == "locked":
            for variables, (orbit, shift) in zip(choices, witness["choices"][:3]):
                pin(formula, variables[0], orbit)
                pin(formula, variables[1], shift)
            first = curve.add(witness["points"][0], witness["points"][1])
            assert first is not None
            pin(formula, mid, onb.toCoords(first[0]))
        return result
    result = build_raw(n, 5, [onb.toCoords(point[0]) for point in preimages], math)
    formula, leaves, mid, _, selector = result
    if mode == "locked":
        for variables, value in zip(leaves, witness["raw_x"][:3]):
            pin(formula, variables, value)
        first = curve.add(witness["raw_points"][0], witness["raw_points"][1])
        raw_sum = curve.add(first, witness["raw_points"][2])
        assert first is not None and raw_sum in preimages
        pin(formula, mid, onb.toCoords(first[0]))
        pin(formula, selector, preimages.index(raw_sum))
    return result


def rss_bytes(pid):
    try:
        output = subprocess.check_output(["/bin/ps", "-o", "rss=", "-p", str(pid)],
                                         stderr=subprocess.DEVNULL).strip()
        return int(output) * 1024 if output else 0
    except (subprocess.CalledProcessError, ValueError):
        return 0


def archive(path):
    path = Path(path)
    compressed = path.with_name(path.name + ".gz")
    size, digest = path.stat().st_size, sha_file(path)
    with compressed.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as sink:
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1 << 20), b""):
                    sink.write(block)
    path.unlink()
    return {"path": compressed.name, "uncompressed_bytes": size,
            "sha256": digest, "compressed_sha256": sha_file(compressed)}


def solve(path, stem, limits):
    command = [str(SOLVER), "--verb", "1", "--threads", "1", "--random", "0",
               "--maxtime", str(limits["solver_seconds"]), "--maxconfl",
               str(limits["max_conflicts"]), str(path)]
    stdout, stderr = HERE / (stem + ".stdout.txt"), HERE / (stem + ".stderr.txt")
    started = time.perf_counter()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen(command, stdout=out, stderr=err)
        peak, stop = 0, None
        while child.poll() is None:
            peak = max(peak, rss_bytes(child.pid))
            elapsed = time.perf_counter() - started
            if peak > limits["rss_mib"] * 1024 * 1024:
                stop = "rss_cap"
            elif elapsed > limits["external_seconds"]:
                stop = "external_timeout"
            if stop:
                child.send_signal(signal.SIGTERM)
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                break
            time.sleep(0.2)
        child.wait()
    wall = time.perf_counter() - started
    output = stdout.read_text(errors="replace")
    reported = re.findall(r"^s\s+(\S+)", output, re.M)
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output, re.M)
    decisions = re.findall(r"^c decisions\s*:\s*(\d+)", output, re.M)
    status = ("BOUNDED_UNKNOWN" if stop or
              (reported and reported[-1] == "INDETERMINATE") else
              "SAT" if reported and reported[-1] == "SATISFIABLE" else
              "UNSAT" if reported and reported[-1] == "UNSATISFIABLE" else
              "PRODUCER_FAILURE")
    model = parse_model(output) if status == "SAT" else None
    logs = {"stdout": archive(stdout), "stderr": archive(stderr)}
    return {"status": status, "stop_reason": stop, "return_code": child.returncode,
            "wall_seconds": wall, "sampled_peak_rss_bytes": peak,
            "conflicts": int(conflicts[-1]) if conflicts else None,
            "decisions": int(decisions[-1]) if decisions else None,
            "search_began": bool(re.search(r"^c rst\s", output, re.M)),
            "command_without_input": command[:-1], "logs": logs}, model


def check_formula(formula, model):
    if model is None:
        return False
    def value(literal):
        bit = bool(model[abs(literal)])
        return bit if literal > 0 else not bit
    return (all(any(value(lit) for lit in clause) for clause in formula.clauses)
            and all((sum(value(bit) for bit in row) & 1) == rhs
                    for row, rhs in formula.xors))


def verify(n, onb, curve, order, keys, public, fixed, target,
           leaves, choices, selector, preimages, model):
    coords = [sum(1 << i for i, bit in enumerate(row) if model[bit])
              for row in leaves]
    unsigned = [curve.pointFromX(onb.fromCoords(value)) for value in coords]
    if any(point is None for point in unsigned):
        return "nonrational_x", None
    choice = decode_choice(selector, model) if selector is not None else None
    raw_target = preimages[choice] if selector is not None else target
    orbit = OrbitKey(onb) if n == 83 else None
    key_set = set(keys)
    for signs in itertools.product((1, -1), repeat=3):
        points = [point if sign > 0 else curve.neg(point)
                  for point, sign in zip(unsigned, signs)]
        raw_sum = curve.add(curve.add(points[0], points[1]), points[2])
        if raw_sum != raw_target:
            continue
        projected = [curve.mul(point, 4) if n == 83 else point for point in points]
        if any(point is None or curve.mul(point, order) is not None
               for point in projected):
            return "invalid_subgroup_projection", None
        if n == 83:
            if not all(0 < x < (1 << n) and x.bit_count() <= 5 for x in coords):
                return "outside_weight_bound", None
            if not all(orbit.canonical(point)[0] in key_set for point in projected):
                return "outside_exact_factor_base", None
        else:
            selected = [decode_base_choice(item, model) for item in choices]
            if not all(onb.frob(onb.fromCoords(keys[index]), shift) == point[0]
                       for (index, shift), point in zip(selected, projected)):
                return "outside_exact_factor_base", None
        total = curve.add(curve.add(projected[0], projected[1]), projected[2])
        if total != target or curve.add(total, fixed) != public:
            return "group_replay_mismatch", None
        return "verified_four_point_relation", {
            "leaf_x_coordinates": coords, "signs": signs,
            "leaf_points": [[str(v) for v in point] for point in projected],
            "fixed_point": [str(v) for v in fixed],
            "remainder": [str(v) for v in target],
            "public_target": [str(v) for v in public],
            "raw_target_choice": choice,
            "distinct_folded_columns": len({
                orbit.canonical(point)[0] for point in [*projected, fixed]
            }) if orbit is not None else None,
        }
    return "no_sign_lift", None


def run(n, mode):
    frozen = check_freeze()
    stem = f"n{n}_{mode}"
    assert not (HERE / (stem + ".json")).exists()
    setup_at = time.perf_counter()
    onb, curve, public, order, keys, witness = load_case(n, mode)
    math = arithmetic(onb)
    kernel = None
    if n == 83:
        kernel, _, _ = kernel_of_cofactor(curve, onb, order, 4, 1404004)
    setup_seconds = time.perf_counter() - setup_at
    query_at = time.perf_counter()
    fixed, selection, pool, group_subtractions = select_fixed(
        n, onb, curve, public, keys, mode, witness, frozen["selection_seed"])
    target = curve.add(public, curve.neg(fixed))
    assert target is not None and curve.add(target, fixed) == public
    preimages = None
    if n == 83:
        preimages, _ = preimage_coset(onb, curve, order, target, kernel)
    target_query_seconds = time.perf_counter() - query_at
    build_at = time.perf_counter()
    # The multiplication table is reusable and excluded from the target clock.
    if n == 53:
        built = build_exact(n, keys, onb.toCoords(target[0]), math)
    else:
        built = build_raw(n, 5, [onb.toCoords(point[0]) for point in preimages], math)
    formula, leaves, mid, choices, selector = built
    if mode == "locked":
        if n == 53:
            for variables, (index, shift) in zip(choices, witness["choices"][:3]):
                pin(formula, variables[0], index)
                pin(formula, variables[1], shift)
            first = curve.add(witness["points"][0], witness["points"][1])
            pin(formula, mid, onb.toCoords(first[0]))
        else:
            for variables, x in zip(leaves, witness["raw_x"][:3]):
                pin(formula, variables, x)
            first = curve.add(witness["raw_points"][0], witness["raw_points"][1])
            raw_sum = curve.add(first, witness["raw_points"][2])
            assert raw_sum in preimages
            pin(formula, mid, onb.toCoords(first[0]))
            pin(formula, selector, preimages.index(raw_sum))
    build_seconds = time.perf_counter() - build_at
    stats = {"variables": formula.variables, "cnf_clauses": len(formula.clauses),
             "xor_rows": len(formula.xors), "and_gates": len(formula.and_cache),
             "free_intermediates": 1, "s3_links": 2}
    formula_path = HERE / (stem + ".xcnf")
    assert not formula_path.exists()
    write_at = time.perf_counter()
    formula.write(formula_path)
    write_seconds = time.perf_counter() - write_at
    limits = frozen["controls"] if mode == "locked" else frozen["search"]
    solver, model = solve(formula_path, stem, limits)
    formula_receipt = archive(formula_path)
    check_at = time.perf_counter()
    checked = check_formula(formula, model)
    lift_status, relation = None, None
    if model is not None:
        assert checked
        lift_status, relation = verify(n, onb, curve, order, keys, public,
                                       fixed, target, leaves, choices,
                                       selector, preimages, model)
    if mode == "locked":
        assert solver["status"] == "SAT" and relation is not None, (solver, lift_status)
    check_seconds = time.perf_counter() - check_at
    receipt = {
        "schema": "q1423-fixed-leaf-run-v1", "proposal_id": "Q1423",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": EXPECTED[n][0],
        "workload_id": EXPECTED[n][1] if mode.startswith("pool") else None,
        "factor_base_actual_B": EXPECTED[n][2],
        "factor_base_folded_columns_K": EXPECTED[n][3],
        "factor_base_enumerated_set_sha256": EXPECTED[n][4],
        "n": n, "mode": mode,
        "public_target": [str(v) for v in public],
        "fixed_point": [str(v) for v in fixed],
        "remainder": [str(v) for v in target],
        "fixed_point_selection": selection,
        "selection_pool_size": pool,
        "charged_group_subtractions": group_subtractions + 1,
        "target_independent_setup_seconds": setup_seconds,
        "target_query_seconds": target_query_seconds,
        "formula_build_seconds": build_seconds,
        "formula_write_seconds": write_seconds,
        "solver_search_seconds": solver["wall_seconds"],
        "target_relation_check_seconds": check_seconds,
        "target_pdp_seconds": (build_seconds + write_seconds + solver["wall_seconds"]
                               if mode.startswith("pool") else None),
        "formula": stats, "formula_archive": formula_receipt,
        "solver": solver, "formula_model_checked": checked,
        "lift_status": lift_status, "verified_relation": relation,
        "natural_relation_yield_estimate": None,
        "field_operations": None,
        "n131_complete_cold_work_log2": None,
        "n131_complete_online_one_target_work_log2": None,
        "freeze_sha256": sha_file(HERE / "freeze.json"),
    }
    (HERE / (stem + ".json")).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(stem, solver["status"], stats, lift_status,
          round(solver["wall_seconds"], 3), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--mode", choices=("locked", "control_unpinned",
                                            "pool1", "pool64"))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.mode is None:
            parser.error("run requires --n and --mode")
        run(args.n, args.mode)


if __name__ == "__main__":
    main()
