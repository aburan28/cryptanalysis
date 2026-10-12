#!/usr/bin/env python3
"""Q1497 frozen N83 external-filter restart hyperparameter sweep."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import platform
import random
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1491 = PARENT / "q20261012_n83_mask_density"
Q1494 = PARENT / "q20261012_n83_pair_base_audit"
Q1495 = PARENT / "q20261012_exact_rationality_filter"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1497_restart_hyperparams_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(result)
    return result


def schedule(protocol: dict) -> dict:
    lo, hi = protocol["leaf_variable_ids_inclusive"]
    population = list(range(lo, hi + 1))
    out = {}
    for group, count in enumerate(protocol["flip_counts"]):
        for replica in range(protocol["replicas_per_count"]):
            phase = protocol["first_phase"] + group * protocol["replicas_per_count"] + replica
            seed = protocol["seed_base"] + phase
            out[str(phase)] = {"flip_count": count, "replica": replica,
                               "seed": seed,
                               "flip_ids": sorted(random.Random(seed).sample(
                                   population, count))}
    assert len(out) == len(set(tuple(x["flip_ids"]) for x in out.values()))
    return out


def freeze() -> None:
    assert not (HERE / "freeze.json").exists()
    protocol = read(HERE / "protocol.json")
    parent, parent_freeze = (read(Q1491 / n) for n in
                             ("build_receipt.json", "freeze.json"))
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_source_sha256"]
    for name in ("selected", "holdout"):
        assert parent_freeze["inputs"][name]["workload_id"] == protocol[
            f"{name}_workload_id"]
    save(HERE / "freeze.json", {
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
        "protocol_sha256": sha(HERE / "protocol.json"),
        "experiment_source_sha256": sha(Path(__file__)),
        "q1491_source_sha256": sha(Q1491 / "sweep.py"),
        "q1491_build_receipt_sha256": sha(Q1491 / "build_receipt.json"),
        "q1491_freeze_sha256": sha(Q1491 / "freeze.json"),
        "q1494_result_sha256": sha(Q1494 / "result.json"),
        "q1495_source_sha256": sha(Q1495 / "filter.py"),
        "q1495_result_sha256": sha(Q1495 / "result.json"),
        "parent_source_path": str(source),
        "parent_source_sha256": sha(source),
        "inputs": parent_freeze["inputs"],
        "mask_schedule": schedule(protocol),
    })
    print("Q1497 frozen", sha(HERE / "freeze.json")[:12])


def replace_once(data: str, old: str, new: str) -> str:
    assert data.count(old) == 1, old[:80]
    return data.replace(old, new)


def patch(path: Path, masks: dict) -> str:
    data = path.read_text()
    data = replace_once(data, "phase < 0 || phase > 48",
                        f"phase < 0 || phase > {max(map(int, masks))}")
    arrays = "\n".join(
        f"static const int_t q1497_mask_{i}[] = {{" +
        ", ".join(map(str, masks[str(i)]["flip_ids"])) + "};"
        for i in sorted(map(int, masks)))
    data = replace_once(data, "static unsigned char q1481_mark[__ID_SIZE__];",
                        arrays + "\nstatic unsigned char q1481_mark[__ID_SIZE__];")
    choices = "\n".join(
        f"    case {i}: flips = q1497_mask_{i}; "
        f"length = sizeof(q1497_mask_{i}) / sizeof(q1497_mask_{i}[0]); break;"
        for i in sorted(map(int, masks)))
    data = replace_once(data, "    default: exit(64);",
                        choices + "\n    default: exit(64);")
    path.write_text(data)
    return sha(path)


def build() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = read(HERE / "freeze.json")
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    assert sha(Path(__file__)) == frozen["experiment_source_sha256"]
    source = Path(frozen["parent_source_path"])
    assert sha(source) == frozen["parent_source_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    modified = patch(BUILD / "src/wdsat.c", frozen["mask_schedule"])
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    save(HERE / "build_receipt.json", {
        "proposal_id": "Q1497", "candidate_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "patched_source_path": str(BUILD / "src/wdsat.c"),
        "patched_source_sha256": modified,
        "binary_path": str(binary), "binary_sha256": sha(binary),
        "config_sha256": sha(BUILD / "src/config.h"),
        "compiler": subprocess.check_output(["gcc", "--version"],
                                            text=True).splitlines()[0],
        "architecture": platform.machine(), "os": platform.platform(),
        "return_code": process.returncode,
        "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
        "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
    })
    print("Q1497 built", sha(binary)[:12])


def exact_usable(bits: str, filt, onb) -> bool:
    leaves = [int(bits[i:i+83][::-1], 2) for i in (0, 83)]
    return all(x and x.bit_count() <= 5 and filt.exact_predicate(onb, x)
               for x in leaves)


def measure() -> None:
    assert not (HERE / "drive_receipt.json").exists()
    protocol, frozen, built = (read(HERE / n) for n in
                               ("protocol.json", "freeze.json", "build_receipt.json"))
    assert sha(HERE / "freeze.json") == built["freeze_sha256"]
    assert sha(Path(__file__)) == frozen["experiment_source_sha256"]
    sweep = module(Q1491 / "sweep.py", "q1491_sweep")
    filt = module(Q1495 / "filter.py", "q1495_filter")
    sweep.HERE = HERE
    onb = filt.CountedOnb(83)
    rows = []
    for phase in sorted(map(int, frozen["mask_schedule"])):
        row = sweep.run_cell("selected", phase, protocol, frozen, built)
        row["proposal_id"] = "Q1497"
        row["point_decomposition_stage_code"] = "PDP4sat"
        row["exact_usable_first_pair"] = (
            exact_usable(row["first_pair_bits"], filt, onb)
            if row["status"] == "FIRST_PAIR_TERMINATED" else None)
        folder = HERE / "runs" / f"selected_phase{phase}"
        save(folder / "receipt.json", row)
        rows.append(row)
        print("Q1497 selected", phase, row["status"],
              row["first_pair_combined_calls"],
              row["exact_usable_first_pair"], flush=True)
    groups = {}
    for count in protocol["flip_counts"]:
        sub = [x for x in rows if x["flip_count"] == count]
        successes = sum(x["exact_usable_first_pair"] is True for x in sub)
        calls = sum(x["first_pair_combined_calls"] or 0 for x in sub)
        eligible = all(x["status"] == "FIRST_PAIR_TERMINATED" for x in sub)
        groups[str(count)] = {"attempts": len(sub), "usable": successes,
                              "first_pair_calls_sum": calls,
                              "calls_per_usable": calls / successes
                              if eligible and successes else None,
                              "censored_or_failed": len(sub) - sum(
                                  x["status"] == "FIRST_PAIR_TERMINATED" for x in sub)}
    eligible = [(v["calls_per_usable"], int(k)) for k, v in groups.items()
                if v["calls_per_usable"] is not None]
    best = min(eligible)[1] if eligible else None
    holdout = []
    if best is not None:
        for phase in sorted(map(int, frozen["mask_schedule"])):
            if frozen["mask_schedule"][str(phase)]["flip_count"] != best:
                continue
            row = sweep.run_cell("holdout", phase, protocol, frozen, built)
            row["proposal_id"] = "Q1497"
            row["point_decomposition_stage_code"] = "PDP4sat"
            row["exact_usable_first_pair"] = (
                exact_usable(row["first_pair_bits"], filt, onb)
                if row["status"] == "FIRST_PAIR_TERMINATED" else None)
            folder = HERE / "runs" / f"holdout_phase{phase}"
            save(folder / "receipt.json", row)
            holdout.append(row)
            print("Q1497 holdout", phase, row["status"],
                  row["first_pair_combined_calls"],
                  row["exact_usable_first_pair"], flush=True)
    save(HERE / "drive_receipt.json", {
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
        "freeze_sha256": sha(HERE / "freeze.json"),
        "build_receipt_sha256": sha(HERE / "build_receipt.json"),
        "selected_summary": groups, "selected_count": best,
        "rows": [{"input": x["input"], "phase": x["phase"],
                  "receipt_sha256": sha(HERE / "runs" /
                                        f"{x['input']}_phase{x['phase']}" /
                                        "receipt.json")}
                 for x in rows + holdout],
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    })
    print("Q1497 selected count", best, groups, flush=True)


def analyze() -> None:
    protocol, frozen, built, drive = (read(HERE / n) for n in
                                      ("protocol.json", "freeze.json",
                                       "build_receipt.json", "drive_receipt.json"))
    assert sha(HERE / "freeze.json") == drive["freeze_sha256"]
    assert sha(HERE / "build_receipt.json") == drive["build_receipt_sha256"]
    filt = module(Q1495 / "filter.py", "q1495_filter")
    onb = filt.CountedOnb(83)
    rows = []
    for entry in drive["rows"]:
        folder = HERE / "runs" / f"{entry['input']}_phase{entry['phase']}"
        receipt = folder / "receipt.json"
        assert sha(receipt) == entry["receipt_sha256"]
        row = read(receipt)
        assert row["proposal_id"] == "Q1497" and row["candidate_id"] is None
        assert row["run_id"] is None and row["isogeny"] == "none"
        assert row["curve_id"] == protocol["curve_id"]
        assert row["factor_base_actual_B"] == protocol["factor_base_actual_B"]
        assert row["factor_base_folded_columns_K"] == protocol[
            "factor_base_folded_columns_K"]
        assert row["workload_id"] == frozen["inputs"][row["input"]]["workload_id"]
        assert row["binary_sha256"] == built["binary_sha256"]
        assert sha(folder / "solver.stderr.txt") == row["stderr_sha256"]
        assert sha(folder / "solver.stdout.txt") == row["stdout_sha256"]
        if row["status"] == "FIRST_PAIR_TERMINATED":
            assert row["search_started"] and row["marker_ok"]
            assert row["exact_usable_first_pair"] == exact_usable(
                row["first_pair_bits"], filt, onb)
        rows.append(row)
    assert len([x for x in rows if x["input"] == "selected"]) == len(
        frozen["mask_schedule"])
    selected = drive["selected_summary"]
    best = drive["selected_count"]
    holdout = [x for x in rows if x["input"] == "holdout"]
    assert len(holdout) == (protocol["replicas_per_count"] if best else 0)
    holdout_usable = sum(x["exact_usable_first_pair"] is True for x in holdout)
    holdout_complete = all(x["status"] == "FIRST_PAIR_TERMINATED" for x in holdout)
    holdout_calls = sum(x["first_pair_combined_calls"] or 0 for x in holdout)
    result = {
        "proposal_id": "Q1497", "candidate_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns_K": protocol["factor_base_folded_columns_K"],
        "point_decomposition_stage_code": "PDP4sat",
        "freeze_sha256": sha(HERE / "freeze.json"),
        "drive_receipt_sha256": sha(HERE / "drive_receipt.json"),
        "selected_summary": selected, "promoted_flip_count": best,
        "holdout_attempts": len(holdout),
        "holdout_usable": holdout_usable,
        "holdout_first_pair_calls_sum": holdout_calls,
        "holdout_calls_per_usable": holdout_calls / holdout_usable
        if holdout_complete and holdout_usable else None,
        "holdout_calls_per_usable_log2": math.log2(
            holdout_calls / holdout_usable) if holdout_complete and
        holdout_usable else None,
        "complete_n83_decomposition_work_log2": None,
        "complete_n131_solve_work_log2": None,
    }
    save(HERE / "result.json", result)
    print("PASS Q1497", best, selected, result["holdout_calls_per_usable"])


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("freeze", "build", "measure", "analyze"):
        raise SystemExit("usage: experiment.py {freeze|build|measure|analyze}")
    globals()[sys.argv[1]]()
