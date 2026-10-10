#!/usr/bin/env python3
"""Replay frozen ordinary Q1420 XCNFs, SAT models, and raw group sums."""

from __future__ import annotations

import argparse
import gzip
from itertools import product
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

import experiment


HERE = experiment.HERE
ref = experiment.ref
sys.path.insert(0, str(experiment.bilinear.SAT))
from verify_model import (literal_value, parse_assignment, read_word,
                          verify_xcnf)  # noqa: E402
sys.path.insert(0, str(experiment.projective.HERE))
import binary_group as group  # noqa: E402


def count_xcnf(path):
    clauses = xors = 0
    with path.open("rb") as stream:
        header = stream.readline().split()
        if len(header) != 4 or header[:2] != [b"p", b"cnf"]:
            raise ValueError("missing XCNF header")
        variables, constraints = map(int, header[2:])
        for line in stream:
            if line.startswith(b"x"):
                xors += 1
            elif line and not line.startswith(b"c"):
                clauses += 1
    if clauses + xors != constraints:
        raise ValueError("XCNF header count differs")
    return {"vars": variables, "clauses": clauses, "xors": xors}


def progress(output):
    rows = [line for line in output.splitlines() if line.startswith("c rst ")]
    conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", output,
                           re.MULTILINE)
    return {"restart_rows": len(rows),
            "last_restart_row": rows[-1] if rows else None,
            "final_conflicts": int(conflicts[-1]) if conflicts else None}


def rational_leaf_point(x, b):
    if x == 0:
        raise ValueError("zero x cannot be a W24 leaf")
    x2 = ref.square(x)
    rhs = x ^ ref.multiply(b, ref.inverse(x2))
    if ref.trace(rhs):
        raise ValueError("leaf x has no rational y")
    t = ref.halftrace(rhs)
    if ref.square(t) ^ t != rhs:
        raise ArithmeticError("halftrace failed leaf equation")
    point = (x, ref.multiply(x, t))
    if not group.on_curve(point, b):
        raise ValueError("leaf point is off curve")
    return point


def replay_group(policy, named, choice, values, cfg):
    alpha, b = ref.coefficients(policy)
    cutoff = ref.read(experiment.projective.HERE / "CONFIG.json")[
        policy + "_last_selected_mask"]
    lifts = ref.read(experiment.finite.ref.HERE / "runs/R1/lifts.json")
    public = tuple(lifts[policy]["public_query"])
    raw_lifts = [tuple(point) for point in lifts[policy]["raw_target_lifts"]]
    if len(raw_lifts) != 4 or any(not group.on_curve(p, b) or
                                 group.times(p, 4, b) != public
                                 for p in raw_lifts):
        raise ValueError("raw lifts do not project to the public query")
    selected_index = sum(literal_value(bit, values) << i
                         for i, bit in enumerate(choice))
    target = raw_lifts[selected_index]
    if read_word("target", ref.DEGREE, named, values) != target[0]:
        raise ValueError("model target x differs from selected public lift")
    masks, leaves = [], []
    r = ref.read(ref.INPUT / "primary_workload.json")["subgroup_order"]
    for i in range(6):
        mask = read_word(f"s{i}", 24, named, values)
        x = read_word(f"x{i}", ref.DEGREE, named, values)
        z = read_word(f"z{i}", ref.DEGREE, named, values)
        if mask == 0 or mask > cutoff or (masks and mask < masks[-1]):
            raise ValueError("decoded mask violates frozen W24 selection")
        exact_x, exact_z, _ = ref.leaf(mask, alpha)
        if (x, z) != (exact_x, exact_z):
            raise ValueError("decoded leaf differs from exact W24 point")
        point = rational_leaf_point(x, b)
        subgroup = group.times(point, 4, b)
        if subgroup is None or group.times(subgroup, r, b) is not None:
            raise ValueError("leaf does not give a usable subgroup point")
        masks.append(mask)
        leaves.append(point)
    nodes = [(read_word(f"t{i}", ref.DEGREE, named, values),
              literal_value(named[f"f:{i}"], values)) for i in range(4)]
    if any(x != 1 for x, finite in nodes if not finite):
        raise ValueError("identity S3 node is not canonical")
    matching = []
    for signs in product((0, 1), repeat=6):
        signed = [group.negate(p) if sign else p
                  for p, sign in zip(leaves, signs)]
        pair01 = group.add(signed[0], signed[1], b)
        pair23 = group.add(signed[2], signed[3], b)
        pair45 = group.add(signed[4], signed[5], b)
        pair0123 = group.add(pair01, pair23, b)
        if [group.projective_x(p) for p in
                (pair01, pair23, pair45, pair0123)] != nodes:
            continue
        total = group.add(pair0123, pair45, b)
        if total == target:
            matching.append(list(signs))
        elif total == group.negate(target):
            matching.append([bit ^ 1 for bit in signs])
    if not matching:
        raise ValueError("model has no signed raw group decomposition")
    signed = [group.negate(p) if bit else p
              for p, bit in zip(leaves, matching[0])]
    total = None
    for point in signed:
        total = group.add(total, point, b)
    if total != target or group.times(total, 4, b) != public:
        raise ValueError("signed group relation misses public target")
    return {
        "selected_lift_index": selected_index,
        "target_raw_point": list(target),
        "public_query": list(public),
        "leaf_masks": masks,
        "distinct_leaf_masks": len(set(masks)),
        "matching_signed_decompositions": len(matching),
        "first_signs_for_public_target": matching[0],
        "intermediates": [{"x": x, "finite": bool(z)} for x, z in nodes],
        "fourfold_projection_verified": True,
    }


def audit_cell(policy, variant, cfg, scratch):
    archive, named_path, frozen_path, frozen = experiment.frozen_formula(
        policy, variant, cfg)
    named = ref.read(named_path)
    if frozen["named_inputs_count"] != len(named):
        raise ValueError("named input map count differs")
    stem = f"{policy}_{variant}"
    solver_path = experiment.RUN / f"{stem}.solver.json"
    stdout_archive = experiment.RUN / f"{stem}.stdout.txt.gz"
    stderr_path = experiment.RUN / f"{stem}.stderr.txt"
    solver = ref.read(solver_path)
    with gzip.open(stdout_archive, "rb") as stream:
        output_bytes = stream.read()
    output = output_bytes.decode("utf-8", errors="replace")
    terminal = [line.strip() for line in output.splitlines()
                if line.startswith("s ")]
    if (solver["schema"] != "ecc2k130-263-bilinear-ordinary-solver-v1"
            or solver["policy"] != policy or solver["variant"] != variant
            or solver["workload_id"] != cfg["workload_id"]
            or solver["formula_sha256"] != frozen["formula_raw_sha256"]
            or solver["formula_receipt_sha256"] != ref.sha(frozen_path)
            or solver["config_sha256"] != ref.sha(HERE / "CONFIG.json")
            or solver["runner_sha256"] != ref.sha(HERE / "experiment.py")
            or solver["solver_sha256"] != cfg["solver_sha256"]
            or solver["command_flags"]
            != ["--threads=1", "--maxtime=120", "--verb=1", "--printsol=1"]
            or solver["threads"] != 1
            or solver["internal_wall_seconds"] != 120
            or solver["external_wall_seconds"] != 150
            or solver["peak_rss_cap_bytes"] != cfg["peak_rss_cap_bytes"]
            or solver["stdout_raw_sha256"]
            != experiment.sha_bytes(output_bytes)
            or solver["stdout_raw_bytes"] != len(output_bytes)
            or solver["stdout_archive_sha256"] != ref.sha(stdout_archive)
            or solver["stdout_archive_bytes"] != stdout_archive.stat().st_size
            or solver["stderr_sha256"] != ref.sha(stderr_path)
            or solver["terminal_status_lines"] != terminal):
        raise ValueError("solver evidence differs from frozen input")
    with tempfile.TemporaryDirectory(prefix="ordinary-audit-", dir=scratch) as temp:
        raw = Path(temp) / "input.xcnf"
        with gzip.open(archive, "rb") as source, raw.open("xb") as target:
            shutil.copyfileobj(source, target, length=1 << 20)
        if (ref.sha(raw) != frozen["formula_raw_sha256"]
                or raw.stat().st_size != frozen["formula_raw_bytes"]):
            raise ValueError("compressed formula differs from committed bytes")
        stats = count_xcnf(raw)
        if stats != frozen["stats"]:
            raise ValueError("XCNF statistics differ from frozen formula")
        trace = progress(output)
        status = solver["status"]
        checks = relation = None
        if status == "SAT_UNVERIFIED":
            if terminal != ["s SATISFIABLE"] or solver["exit_code"] != 10:
                raise ValueError("SAT terminal result is incomplete")
            values = parse_assignment(output, stats["vars"])
            checks = verify_xcnf(raw, values)
            relation = replay_group(
                policy, named, frozen["target_selector_variables"],
                values, cfg)
            status = "SAT_VERIFIED_GROUP"
        elif status == "BOUNDED_UNKNOWN":
            if not (solver["guard"] == "WALL_CAP" or
                    terminal == ["s INDETERMINATE"] and
                    solver["exit_code"] == 15):
                raise ValueError("bounded status lacks a recorded cap")
            if trace["restart_rows"] == 0:
                raise ValueError("bounded status lacks solver search progress")
        elif status == "UNSAT":
            if terminal != ["s UNSATISFIABLE"] or solver["exit_code"] != 20:
                raise ValueError("UNSAT terminal result is incomplete")
        elif status == "OOM_GUARD":
            if solver["guard"] != "RSS_CAP":
                raise ValueError("RSS status lacks a guard")
        elif status != "PRODUCER_FAILURE":
            raise ValueError("unknown solver status")
    return {
        "status": status, "raw_status": solver["status"],
        "formula_sha256": frozen["formula_raw_sha256"],
        "formula_stats": frozen["stats"],
        "build_wall_seconds": frozen["build_wall_seconds"],
        "solver_wall_seconds": solver["wall_seconds"],
        "guard": solver["guard"], "exit_code": solver["exit_code"],
        "peak_sampled_rss_bytes": solver["peak_sampled_rss_bytes"],
        "search_progress": trace,
        "xcnf_checks": checks,
        "group_replay": relation,
        "verified_decomposition": relation is not None,
        "novel_rank": None,
        "solver_receipt_sha256": ref.sha(solver_path),
        "stdout_archive_sha256": ref.sha(stdout_archive),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-dir", type=Path,
                        default=Path("/private/tmp"))
    args = parser.parse_args()
    if not args.scratch_dir.is_dir():
        parser.error("scratch directory does not exist")
    cfg = experiment.checked_config()
    panels = {}
    for policy, variant in cfg["run_order"]:
        panels[f"{policy}_{variant}"] = audit_cell(
            policy, variant, cfg, args.scratch_dir)
    result = {
        "schema": "ecc2k130-263-bilinear-ordinary-audit-v1",
        "status": "PASS_EXACT_INPUTS_AND_TRANSCRIPTS",
        "candidate_id": None,
        "workload_id": cfg["workload_id"],
        "query_index": 0,
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "producer_sha256": ref.sha(HERE / "experiment.py"),
        "auditor_sha256": ref.sha(Path(__file__)),
        "panels": panels,
    }
    experiment.save_json(experiment.RUN / "audit.json", result)
    print(json.dumps({key: {"status": row["status"],
                            "verified_decomposition": row[
                                "verified_decomposition"]}
                      for key, row in panels.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
