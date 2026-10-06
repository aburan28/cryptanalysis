#!/usr/bin/env python3
"""Q1415: run Q1410's exact ordinary XCNF with XOR Gaussian reasoning."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from run_probe import HERE, sha

PROTOCOL = HERE / "q1415_gauss_n53_protocol.json"
PARENT_PROTOCOL = HERE / "q1410_balanced_s3_n53_protocol.json"
PARENT_RUN = HERE / "runs/n53_q1410_ordinary.json"
FORMULA = HERE / "runs/n53_q1410_ordinary.xcnf.gz"
RUNTIME = HERE / "q1415_sage_runtime_info.json"
OUT = HERE / "runs/n53_q1415_gauss_ordinary.json"
STDOUT = HERE / "runs/n53_q1415_gauss_ordinary.stdout.txt"
STDERR = HERE / "runs/n53_q1415_gauss_ordinary.stderr.txt"


def identity_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main():
    assert not OUT.exists() and not STDOUT.exists() and not STDERR.exists()
    protocol = json.loads(PROTOCOL.read_text())
    parent_protocol = json.loads(PARENT_PROTOCOL.read_text())
    parent = json.loads(PARENT_RUN.read_text())
    assert protocol["proposal_id"] == "Q1415"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["parent_protocol_sha256"] == sha(PARENT_PROTOCOL)
    assert protocol["parent_run_sha256"] == sha(PARENT_RUN)
    assert protocol["formula_archive_sha256"] == sha(FORMULA)
    assert protocol["runtime_info_sha256"] == sha(RUNTIME)
    assert json.loads(RUNTIME.read_text())["status"] == "verified"
    for name in ("curve_id", "factor_base_actual_B",
                 "factor_base_folded_columns",
                 "factor_base_enumerated_set_sha256"):
        assert protocol[name] == parent[name]
    assert protocol["ordinary_workload_id"] == parent["workload_id"]
    assert parent["protocol_sha256"] == sha(PARENT_PROTOCOL)
    assert parent["status"] == "censored"
    assert len(parent["attempts"]) == 1
    original = parent["attempts"][0]
    assert original["xcnf_sha256"] == protocol["formula_raw_sha256"]
    assert original["xcnf_bytes"] == protocol["formula_raw_bytes"]
    binary = Path(shutil.which("cryptominisat5"))
    assert sha(binary) == protocol["solver_binary_sha256"]
    assert protocol["solver_flags"] == [
        "--verb", "1", "--threads", "1", "--maxconfl", "1000000",
        "--maxmatrixcols", "10000", "--autodisablegauss", "0"]
    with tempfile.TemporaryDirectory(prefix="q1415_", dir="/private/tmp") as tmp:
        formula_path = Path(tmp) / "ordinary.xcnf"
        digest = hashlib.sha256()
        formula_bytes = 0
        with gzip.open(FORMULA, "rb") as compressed, formula_path.open("wb") as raw:
            for chunk in iter(lambda: compressed.read(1 << 20), b""):
                digest.update(chunk)
                raw.write(chunk)
                formula_bytes += len(chunk)
        assert digest.hexdigest() == protocol["formula_raw_sha256"]
        assert formula_bytes == protocol["formula_raw_bytes"]
        command = [str(binary), *protocol["solver_flags"], str(formula_path)]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.perf_counter()
        try:
            result = subprocess.run(command, capture_output=True,
                                    timeout=protocol["external_wall_cap_seconds"])
            stdout = result.stdout.decode(errors="replace")
            stderr = result.stderr.decode(errors="replace")
            code = result.returncode
            status = "sat_unverified" if code == 10 else (
                "unsat" if code == 20 else "censored")
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
            code, status = None, "external_timeout"
        solver_wall = time.perf_counter() - started
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
    STDOUT.write_text(stdout)
    STDERR.write_text(stderr)
    conflicts = re.findall(r"conflicts\s*[:=]\s*([0-9]+)", stdout,
                           flags=re.IGNORECASE)
    matrix_used = bool(re.search(
        r"Using [1-9][0-9]* matrices recovered", stdout))
    point_decomposition = {
        **parent_protocol["point_decomposition"],
        "formula_raw_sha256": protocol["formula_raw_sha256"],
        "solver_flags": protocol["solver_flags"],
        "solver_binary_sha256": protocol["solver_binary_sha256"],
        "source_sha256": protocol["source_sha256"],
        "external_wall_cap_seconds": protocol["external_wall_cap_seconds"],
    }
    identity = {
        "factor_base": parent_protocol["factor_base"],
        "point_decomposition": point_decomposition,
    }
    full_digest = identity_hash(identity)
    stage_id = f"PS1N53Ckb1fb{protocol['factor_base_actual_B']}PDP4sath{full_digest[:12]}"
    wid = protocol["ordinary_workload_id"]
    receipt = {
        "kind": "q1415_q1410_formula_gaussian_solver_probe",
        "proposal_id": "Q1415", "candidate_id": None,
        "stage_config_id": stage_id,
        "stage_config_sha256_full": full_digest,
        "stage_config_hash_input": identity,
        "workload_id": wid,
        "run_id": None,
        "stage_run_id": f"{stage_id}W{wid}R1",
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "factor_base_actual_B": protocol["factor_base_actual_B"],
        "factor_base_folded_columns": protocol["factor_base_folded_columns"],
        "factor_base_enumerated_set_sha256": protocol[
            "factor_base_enumerated_set_sha256"],
        "same_ordinary_target_and_formula_as_q1410": True,
        "formula_archive_sha256": sha(FORMULA),
        "formula_raw_sha256": protocol["formula_raw_sha256"],
        "solver_command": command,
        "solver_binary_sha256": sha(binary),
        "solver_status": status,
        "solver_return_code": code,
        "solver_wall_seconds_exploratory": solver_wall,
        "solver_conflicts_reported": int(conflicts[-1]) if conflicts else None,
        "gaussian_matrix_reported_active": matrix_used,
        "peak_child_rss_raw": after.ru_maxrss,
        "peak_child_rss_units": "bytes on Darwin, KiB on Linux",
        "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
        "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
        "solver_stdout_sha256": sha(STDOUT),
        "solver_stderr_sha256": sha(STDERR),
        "observed_verified_relation_count": 0 if status != "sat_unverified" else None,
        "natural_relation_yield_estimate": None,
        "complete_solve_work_log2": None,
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(RUNTIME),
        "source_sha256": sha(Path(__file__)),
    }
    OUT.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": status,
                      "gaussian_matrix_reported_active": matrix_used,
                      "conflicts": receipt["solver_conflicts_reported"],
                      "seconds": solver_wall}))


if __name__ == "__main__":
    main()
