#!/usr/bin/env python3
"""Q1424 frozen CryptoMiniSat parameter screen on four-leaf S3 XCNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/compact-s3-m4-20261003"
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))

from chain_s3_base_orbit import build_base_orbit_chain, decode_base_choice  # noqa: E402
from chain_s3_multitarget import build_multitarget  # noqa: E402
from q1325_inputs import read_inputs as read_n83  # noqa: E402
from run_base_orbit_probe import read_inputs as read_n53  # noqa: E402
from run_probe import curves, field, lift, parse_model  # noqa: E402
from run_q1404_raw_preimage_w5 import verify_model as verify_n83  # noqa: E402

SOLVER = Path(shutil.which("cryptominisat5") or "/opt/homebrew/bin/cryptominisat5")
VARIANTS = {
    "baseline": (),
    "seed17": ("--random", "17"),
    "polarfalse": ("--polar", "false"),
    "polarrnd": ("--polar", "rnd"),
    "restartgeom": ("--restart", "geom"),
    "restartluby": ("--restart", "luby"),
    "vsids": ("--branchstr", "vsids1+vsids2"),
    "gausswide": ("--maxmatrixcols", "10000", "--autodisablegauss", "0"),
}
N83_VARIANTS = ("baseline", "seed17", "restartluby", "gausswide")
CASE = {
    53: {"curve_id": "EC1N53Ckb1hf77aab617904",
         "workload_id": "74f2979b3e68", "B": 24062, "K": 227,
         "base_digest": "05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5",
         "ordinary_receipt": "runs/n53_ordinary_exact_base_orbit.json",
         "ordinary_formula": "runs/n53_ordinary_exact_base_orbit.xcnf.gz"},
    83: {"curve_id": "EC1N83Ckb1h876c2921cb64",
         "workload_id": "bab50a1e5f66", "B": 30977592, "K": 186612,
         "base_digest": "56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8",
         "ordinary_receipt": "runs/n83_q1404_ordinary.json",
         "ordinary_formula": "runs/n83_q1404_ordinary.xcnf.gz"},
}
OLD_SOURCES = (
    "chain_s3.py", "chain_s3_base_orbit.py", "chain_s3_factored.py",
    "chain_s3_ordered.py", "chain_s3_orbit.py", "chain_s3_multitarget.py",
    "q1325_inputs.py", "run_base_orbit_probe.py", "run_probe.py",
    "run_q1404_raw_preimage_w5.py", "cofactor_preimages.py",
)
ROOT_SOURCES = (
    "ecc2k130/codegen/field.py", "ecc2k130/codegen/curves.py",
    "experiments/koblitz-pair-claw-20260929/orbit_key.py",
)
INPUTS = (
    "runs/n53_ordinary_exact_base_orbit.json",
    "runs/n53_ordinary_exact_base_orbit.xcnf.gz",
    "runs/n53_ordinary_frozen.json", "bases/n53_weight3_orbits.json.gz",
    "runs/n83_q1404_ordinary.json", "runs/n83_q1404_ordinary.xcnf.gz",
    "runs/n83_ordinary_frozen.json", "runs/n83_ordinary_raw_preimages.json",
    "bases/n83_weight5_full_orbits.json",
    "bases/n83_weight5_full_point_orbits.bin", "protocol.json",
    "q1419_partial_pin/runs/n53_full_lock/receipt.json",
    "q1419_partial_pin/runs/n53_full_lock/system.xcnf.gz",
    "q1419_partial_pin/runs/n83_full_lock/receipt.json",
    "q1419_partial_pin/runs/n83_full_lock/system.xcnf.gz",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def freeze():
    assert SOLVER.is_file()
    for n, case in CASE.items():
        receipt = json.loads((OLD / case["ordinary_receipt"]).read_text())
        raw = gzip.decompress((OLD / case["ordinary_formula"]).read_bytes())
        expected = (receipt["xcnf_sha256"] if n == 53 else
                    receipt["attempts"][0]["xcnf_sha256"])
        assert sha(raw) == expected
        assert receipt["curve_id"] == case["curve_id"]
        assert receipt["workload_id"] == case["workload_id"]
        assert (receipt["factor_base_actual_B"],
                receipt["factor_base_folded_columns"],
                receipt["factor_base_enumerated_set_sha256"]) == (
            case["B"], case["K"], case["base_digest"])
    result = {
        "schema": "q1424-solver-grid-freeze-v1", "proposal_id": "Q1424",
        "candidate_id": None, "isogeny": "none",
        "protocol_sha256": sha_file(HERE / "PROTOCOL.md"),
        "runner_sha256": sha_file(__file__),
        "solver_binary": str(SOLVER.resolve()),
        "solver_binary_sha256": sha_file(SOLVER),
        "old_source_sha256": {name: sha_file(OLD / name) for name in OLD_SOURCES},
        "root_source_sha256": {name: sha_file(ROOT / name) for name in ROOT_SOURCES},
        "input_sha256": {name: sha_file(OLD / name) for name in INPUTS},
        "variants": VARIANTS, "n83_variants": N83_VARIANTS,
        "ordinary_limits": {"max_conflicts": 200000, "solver_seconds": 45,
                            "external_seconds": 55, "rss_mib": 1536},
        "control_limits": {"max_conflicts": 200000, "solver_seconds": 10,
                           "external_seconds": 15, "rss_mib": 1536},
        "cases": CASE,
    }
    path = HERE / "freeze.json"
    assert not path.exists()
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(sha_file(path))


def check_freeze():
    frozen = json.loads((HERE / "freeze.json").read_text())
    assert frozen["proposal_id"] == "Q1424"
    assert frozen["protocol_sha256"] == sha_file(HERE / "PROTOCOL.md")
    assert frozen["runner_sha256"] == sha_file(__file__)
    assert frozen["solver_binary_sha256"] == sha_file(SOLVER)
    assert all(sha_file(OLD / name) == value
               for name, value in frozen["old_source_sha256"].items())
    assert all(sha_file(ROOT / name) == value
               for name, value in frozen["root_source_sha256"].items())
    assert all(sha_file(OLD / name) == value
               for name, value in frozen["input_sha256"].items())
    return frozen


def ps_rss_bytes(pid):
    try:
        out = subprocess.check_output(["/bin/ps", "-o", "rss=", "-p", str(pid)],
                                      stderr=subprocess.DEVNULL).strip()
        return int(out) * 1024 if out else 0
    except (ValueError, subprocess.CalledProcessError):
        return 0


def archive(path):
    path = Path(path)
    data = path.read_bytes()
    compressed = path.with_name(path.name + ".gz")
    with compressed.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as sink:
            sink.write(data)
    path.unlink()
    return {"path": compressed.name, "sha256": sha(data),
            "bytes": len(data), "archive_sha256": sha_file(compressed)}


def check_xcnf_model(data, model):
    """Independently evaluate the serialized native-XOR XCNF assignment."""
    assert model is not None
    clauses = xors = 0
    header = data.split(b"\n", 1)[0].split()
    assert header[:2] == [b"p", b"cnf"]
    for line in data.splitlines()[1:]:
        if not line or line.startswith(b"c"):
            continue
        parts = line.split()
        assert parts[-1] == b"0"
        if parts[0].startswith(b"x"):
            rhs = not parts[0].startswith(b"x-")
            first = int(parts[0][2:] if not rhs else parts[0][1:])
            variables = [first] + [int(value) for value in parts[1:-1]]
            assert all(0 < var <= int(header[2]) for var in variables)
            assert (sum(bool(model.get(var, False)) for var in variables) & 1) == rhs
            xors += 1
        else:
            row = [int(value) for value in parts[:-1]]
            assert any((model.get(abs(lit), False) if lit > 0 else
                        not model.get(abs(lit), False)) for lit in row)
            clauses += 1
    assert clauses + xors == int(header[3])
    return {"variables": int(header[2]), "clauses": clauses, "xors": xors}


def solve(xcnf, stem, flags, limits):
    command = [str(SOLVER), "--verb", "1", "--threads", "1",
               "--maxtime", str(limits["solver_seconds"]), "--maxconfl",
               str(limits["max_conflicts"])]
    if "--random" not in flags:
        command.extend(("--random", "0"))
    command.extend((*flags, str(xcnf)))
    stdout = HERE / f"{stem}.stdout.txt"
    stderr = HERE / f"{stem}.stderr.txt"
    started = time.perf_counter()
    with stdout.open("wb") as out, stderr.open("wb") as err:
        child = subprocess.Popen(command, stdout=out, stderr=err)
        stop, peak = None, 0
        while child.poll() is None:
            peak = max(peak, ps_rss_bytes(child.pid))
            if peak > limits["rss_mib"] * 1024 * 1024:
                stop = "rss_cap"
            elif time.perf_counter() - started > limits["external_seconds"]:
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
    elapsed = time.perf_counter() - started
    output = stdout.read_text(errors="replace")
    status_lines = re.findall(r"^s\s+(\S+)", output, re.M)
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output, re.M)
    decisions = re.findall(r"^c decisions\s*:\s*(\d+)", output, re.M)
    propagations = re.findall(r"^c propagations\s*:\s*(\d+)", output, re.M)
    state = ("BOUNDED_UNKNOWN" if stop or
             (status_lines and status_lines[-1] == "INDETERMINATE") else
             "SAT" if status_lines and status_lines[-1] == "SATISFIABLE" else
             "UNSAT" if status_lines and status_lines[-1] == "UNSATISFIABLE" else
             "PRODUCER_FAILURE")
    model = parse_model(output) if state == "SAT" else None
    logs = {"stdout": archive(stdout), "stderr": archive(stderr)}
    return {"status": state, "stop_reason": stop,
            "return_code": child.returncode, "wall_seconds": elapsed,
            "sampled_peak_rss_bytes": peak,
            "conflicts": int(conflicts[-1]) if conflicts else None,
            "decisions": int(decisions[-1]) if decisions else None,
            "propagations": int(propagations[-1]) if propagations else None,
            "search_began": bool(re.search(r"^c rst\s", output, re.M)),
            "command_without_input": command[:-1], "logs": logs}, model


def verify_relation(n, formula_data, model, case):
    if n == 53:
        _, baseline, _, _, keys = read_n53(53, "ordinary")
        public = tuple(map(int, baseline["public_subgroup_target"]))
        onb, curve = field.Onb(53), None
        curve = curves.Curve(onb)
        built, leaves, _, choices = build_base_orbit_chain(
            53, keys, onb.toCoords(public[0]))
        selected = [decode_base_choice(item, model) for item in choices]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "check.xcnf"
            built.write(path)
            assert path.read_bytes() == formula_data
        coords, relation, status = lift(onb, curve, leaves, model,
                                        public, public, 1)
        if relation is not None:
            order = int(json.loads(gzip.decompress((OLD / "bases/n53_weight3_orbits.json.gz").read_bytes()))["curve"]["subgroup_order"])
            assert all(curve.mul(tuple(map(int, point)), order) is None
                       for point in relation["projected_points"])
            assert all(0 <= index < len(keys) and 0 <= shift < 53
                       for index, shift in selected)
        return {"lift_status": status, "leaf_x_coordinates": coords,
                "orbit_choices": selected, "relation": relation}
    _, base, _, keys, _, baseline = read_n83()
    public = tuple(map(int, baseline["public_subgroup_target"]))
    source = json.loads((OLD / "runs/n83_q1404_ordinary.json").read_text())
    raw_xs = source["raw_preimage_x_coordinates"]
    built, leaves, _, _, selector = build_multitarget(83, 5, raw_xs)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "check.xcnf"
        built.write(path)
        assert path.read_bytes() == formula_data
    onb = field.Onb(83)
    curve = curves.Curve(onb)
    order = int(base["curve"]["subgroup_order"])
    raw_points = [tuple(map(int, point)) for point in json.loads(
        (OLD / "runs/n83_ordinary_raw_preimages.json").read_text())[
            "raw_target_points"]]
    choice, raw_x, coords, status, relation, distinct = verify_n83(
        onb, curve, order, set(keys), public, raw_points, raw_xs,
        leaves, selector, model)
    return {"lift_status": status, "leaf_x_coordinates": coords,
            "raw_target_choice": choice, "raw_target_x": raw_x,
            "four_distinct_columns": distinct, "relation": relation}


def run(n, variant):
    frozen = check_freeze()
    assert variant in VARIANTS
    assert n == 53 or variant in N83_VARIANTS
    case = CASE[n]
    stem = f"n{n}_{variant}"
    receipt_path = HERE / f"{stem}.json"
    assert not receipt_path.exists()
    ordinary_data = gzip.decompress((OLD / case["ordinary_formula"]).read_bytes())
    control_path = OLD / f"q1419_partial_pin/runs/n{n}_full_lock/system.xcnf.gz"
    control_data = gzip.decompress(control_path.read_bytes())
    flags = VARIANTS[variant]
    with tempfile.TemporaryDirectory(prefix="q1424-", dir=HERE) as directory:
        ordinary = Path(directory) / "ordinary.xcnf"
        control = Path(directory) / "control.xcnf"
        ordinary.write_bytes(ordinary_data)
        control.write_bytes(control_data)
        control_result, control_model = solve(
            control, stem + ".control", flags, frozen["control_limits"])
        control_checked = (check_xcnf_model(control_data, control_model)
                           if control_model is not None else None)
        ordinary_result, model = solve(
            ordinary, stem + ".ordinary", flags, frozen["ordinary_limits"])
    model_checked = check_xcnf_model(ordinary_data, model) if model else None
    checked_relation = (verify_relation(n, ordinary_data, model, case)
                        if model_checked else None)
    receipt = {
        "schema": "q1424-solver-grid-run-v1", "proposal_id": "Q1424",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "curve_id": case["curve_id"], "workload_id": case["workload_id"],
        "factor_base_actual_B": case["B"], "factor_base_folded_columns_K": case["K"],
        "factor_base_enumerated_set_sha256": case["base_digest"],
        "n": n, "variant": variant, "solver_flags": flags,
        "ordinary_formula_sha256": sha(ordinary_data),
        "ordinary_formula_archive_sha256": sha_file(OLD / case["ordinary_formula"]),
        "control_formula_sha256": sha(control_data),
        "control_formula_archive_sha256": sha_file(control_path),
        "control": control_result, "control_model_checked": control_checked,
        "ordinary": ordinary_result, "ordinary_model_checked": model_checked,
        "ordinary_relation_check": checked_relation,
        "verified_natural_relation_count": int(bool(checked_relation and
                                                    checked_relation["relation"])),
        "field_operations": None, "natural_relation_yield_estimate": None,
        "cost_per_useful_row": None, "n131_complete_solve_work_log2": None,
        "freeze_sha256": sha_file(HERE / "freeze.json"),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(stem, ordinary_result["status"], ordinary_result["conflicts"],
          round(ordinary_result["wall_seconds"], 3),
          "relation", receipt["verified_natural_relation_count"], flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "run"))
    parser.add_argument("--n", type=int, choices=(53, 83))
    parser.add_argument("--variant", choices=tuple(VARIANTS))
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    else:
        if args.n is None or args.variant is None:
            parser.error("run requires --n and --variant")
        run(args.n, args.variant)


if __name__ == "__main__":
    main()
