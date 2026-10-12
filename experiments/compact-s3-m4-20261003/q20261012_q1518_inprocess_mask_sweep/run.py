#!/usr/bin/env python3
"""Sweep frozen N83 leaf masks with Q1517 in-process pair enumeration."""
import gzip
import hashlib
import importlib.util
import json
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
Q1508 = PARENT / "q20261012_n83_blocked_pair_handoff"
Q1517 = PARENT / "q20261012_q1517_inprocess_pair_enum"
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
BASE_MANIFEST = PARENT / "bases/n83_weight5_full_orbits.json"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


prior = module("q1517_run", Q1517 / "run.py")
base_runner = module("q1508_run", Q1508 / "run.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    p = read(HERE / "protocol.json")
    frozen = read(Q1488 / "freeze.json")
    build = read(Q1517 / "build_receipt.json")
    binary = Path(build["binary_path"])
    assert sha(Q1488 / "freeze.json") == p["q1488_freeze_sha256"]
    assert sha(Q1517 / "build_receipt.json") == p["q1517_build_receipt_sha256"]
    assert sha(binary) == build["binary_sha256"]
    assert sha(BASE) == p["factor_base_point_file_sha256"]
    assert sha(BASE_MANIFEST) == p["factor_base_manifest_sha256"]
    assert not (HERE / "result.json").exists()
    raw_base = BASE.read_bytes()
    keys = {int.from_bytes(raw_base[i:i + 21], "little")
            for i in range(0, len(raw_base), 21)}
    assert len(keys) == p["factor_base_folded_columns_K"]
    onb = base_runner.CountedOnb(83)
    curve, orbit = base_runner.Curve(onb), base_runner.OrbitKey(onb)
    order = int(read(BASE_MANIFEST)["curve"]["subgroup_order"])
    rows = []
    for label in p["inputs"]:
        cell = frozen["inputs"][label]
        raw = gzip.decompress(Path(cell["derived_path"]).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == cell["derived_raw_sha256"]
        label_folder = HERE / "runs" / label
        label_folder.mkdir(parents=True, exist_ok=False)
        system = label_folder / "system.xcnf"
        system.write_bytes(raw)
        (label_folder / "system.xcnf.gz").write_bytes(gzip.compress(raw, mtime=0))
        for phase in p["mask_phases"]:
            folder = label_folder / f"phase{phase}"
            folder.mkdir()
            out, err = folder / "solver.stdout.txt", folder / "solver.stderr.txt"
            env = os.environ.copy()
            env.update(Q1469_ORDER_MODE="q1507_target_leaf_first",
                       Q1472_PHASE_INDEX="0", Q1473_SELECTOR_PHASE="0",
                       Q1481_LEAF_MASK=str(phase))
            started, reason, usage = time.monotonic(), None, None
            with out.open("wb") as stdout, err.open("wb") as stderr:
                child = subprocess.Popen([str(binary), "-i", str(system)],
                                         stdout=stdout, stderr=stderr, env=env,
                                         preexec_fn=prior.cpu_limit(
                                             p["cpu_soft_seconds_per_cell"],
                                             p["cpu_hard_seconds_per_cell"]))
                deadline, sent_at = started + p["wall_seconds_per_cell"], None
                while True:
                    pid, status, usage = os.wait4(child.pid, os.WNOHANG)
                    if pid:
                        child.returncode = os.waitstatus_to_exitcode(status)
                        break
                    now = time.monotonic()
                    if sent_at is None and now >= deadline:
                        reason = "WALL_CAP"
                        child.terminate()
                        sent_at = now
                    elif sent_at is not None and now - sent_at > 5:
                        child.kill()
                    time.sleep(0.05)
            stderr_data = err.read_bytes()
            markers = [(int(a), int(b), int(c), int(d), e.decode())
                       for a, b, c, d, e in prior.PAIR.findall(stderr_data)]
            outcomes = []
            for _, _, _, _, bits in markers:
                leaves = base_runner.base_pair(bits, onb, curve, orbit, keys, order)
                outcomes.append({"bits": bits,
                                 "both_exact_base_usable": all(
                                     x["exact_base_member"] for x in leaves),
                                 "leaves": [{k: v for k, v in x.items() if k != "point"}
                                            for x in leaves]})
            status_name = ("EIGHT_PAIRS_TERMINATED" if child.returncode == 47
                           and len(markers) == 8 else
                           "WALL_CAP_SEARCH_STARTED" if reason == "WALL_CAP" and
                           b"Q1458_SEARCH_START" in stderr_data else
                           "CPU_CAP_SEARCH_STARTED" if child.returncode in
                           (-signal.SIGXCPU, -signal.SIGKILL) else
                           "BRANCH_CAP_SEARCH_STARTED" if child.returncode == 42 else
                           "PROCESS_FAILURE")
            last_calls = markers[-1][2] + markers[-1][3] if markers else None
            row = {"input": label, "workload_id": cell["workload_id"],
                   "phase": phase, "flip_count": len(frozen["mask_schedule"][str(phase)]["flip_ids"]),
                   "status": status_name, "return_code": child.returncode,
                   "termination_reason": reason,
                   "pairs": [{"index": a, "branch": b, "cnf_calls": c,
                              "xor_calls": d, "bits": e} for a, b, c, d, e in markers],
                   "exact_base_outcomes": outcomes,
                   "distinct_pairs": len(set(x[4] for x in markers)),
                   "exact_base_usable_pairs": sum(x["both_exact_base_usable"] for x in outcomes),
                   "cnf_xor_calls_to_last_pair": last_calls,
                   "calls_per_usable_pair": last_calls / sum(
                       x["both_exact_base_usable"] for x in outcomes) if last_calls
                       and any(x["both_exact_base_usable"] for x in outcomes) else None,
                   "search_started": b"Q1458_SEARCH_START" in stderr_data,
                   "wall_seconds_exploratory": time.monotonic() - started,
                   "child_user_cpu_seconds": usage.ru_utime,
                   "child_system_cpu_seconds": usage.ru_stime,
                   "child_peak_rss_bytes_darwin": usage.ru_maxrss,
                   "stdout_sha256": sha(out), "stderr_sha256": sha(err)}
            save(folder / "receipt.json", row)
            rows.append(row)
            save(HERE / "result.partial.json", {"proposal_id": "Q1518", "rows": rows})
            print(label, phase, status_name, len(markers),
                  row["exact_base_usable_pairs"], last_calls, flush=True)
        system.unlink()
    save(HERE / "result.json", {"proposal_id": "Q1518", "candidate_id": None,
                                "run_id": None, "curve_id": p["curve_id"],
                                "isogeny": "none", "point_decomposition_stage_code": "PDP4sat",
                                "protocol_sha256": sha(HERE / "protocol.json"),
                                "run_source_sha256": sha(Path(__file__)),
                                "rows": rows, "complete_n83_decomposition_work_log2": None,
                                "complete_n131_solve_work_log2": None})


if __name__ == "__main__":
    main()
