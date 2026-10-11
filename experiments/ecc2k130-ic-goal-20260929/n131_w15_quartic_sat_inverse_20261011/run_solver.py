"""Bounded one-worker search for an unpinned positive quartic product root."""

import gzip
import json
import resource
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import psutil

import build

HERE = Path(__file__).resolve().parent
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def main():
    protocol_path = HERE / "solver_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "solver": SOLVER,
             "formula": HERE / "factor0.xcnf.gz",
             "build": HERE / "factor0_build.json",
             "audit": HERE / "audit_result.json"}
    assert protocol["status"] == "FROZEN_BEFORE_POSITIVE_QUARTIC_SOLVER"
    assert protocol["source_sha256"] == {name: build.sha(path)
                                          for name, path in paths.items()}
    assert protocol["worker_count"] == 1
    profile = json.loads(paths["build"].read_text())
    audit = json.loads(paths["audit"].read_text())
    assert audit["status"] == "PASS_FULL_POSITIVE_QUARTIC_XCNF_ASSIGNMENT"
    assert profile["formula_gzip_sha256"] == build.sha(paths["formula"])
    out_path = HERE / "solver.stdout.txt"
    err_path = HERE / "solver.stderr.txt"
    with tempfile.TemporaryDirectory(prefix="n131_w15_quartic_sat_", dir="/private/tmp") as tmp:
        formula = Path(tmp) / "factor0.xcnf"
        with gzip.open(paths["formula"], "rb") as inp, formula.open("wb") as out:
            shutil.copyfileobj(inp, out, 1 << 20)
        assert build.sha(formula) == audit["formula_sha256"]
        command = [str(SOLVER), "--threads=1",
                   f"--maxtime={protocol['solver_cap_seconds']}",
                   "--zero-exit-status", "--verb=1", "--printsol=1", str(formula)]
        started = time.monotonic_ns()
        peak, stop_reason = 0, None
        with out_path.open("x") as out, err_path.open("x") as err:
            process = subprocess.Popen(command, stdout=out, stderr=err)
            child = psutil.Process(process.pid)
            while process.poll() is None:
                try:
                    peak = max(peak, child.memory_info().rss)
                except psutil.NoSuchProcess:
                    break
                if peak > protocol["rss_cap_bytes"]:
                    stop_reason = "RSS_CAP"
                elif time.monotonic_ns() - started > protocol["parent_cap_seconds"] * 10**9:
                    stop_reason = "PARENT_TIMEOUT"
                if stop_reason:
                    process.kill()
                    break
                time.sleep(0.05)
            exit_code = process.wait()
        wall_ns = time.monotonic_ns() - started
    stdout = out_path.read_text()
    status = stop_reason or ("SAT_MODEL_UNAUDITED" if "s SATISFIABLE" in stdout
                             else "UNSAT" if "s UNSATISFIABLE" in stdout
                             else "BOUNDED_UNKNOWN")
    result = {"status": status, "candidate_id": None,
              "command": command, "exit_code": exit_code,
              "solver_wall_ns": wall_ns, "peak_sampled_child_rss_bytes": peak,
              "peak_child_rss_bytes": max(peak, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
              "stdout_sha256": build.sha(out_path), "stderr_sha256": build.sha(err_path),
              "formula_sha256": audit["formula_sha256"],
              "protocol_sha256": build.sha(protocol_path)}
    (HERE / "solver_result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": status, "solver_wall_ns": wall_ns,
                      "peak_child_rss_bytes": result["peak_child_rss_bytes"]}))


if __name__ == "__main__":
    main()
