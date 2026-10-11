"""Solve one source-bound pinned pair-output XCNF as a wiring control."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import psutil


HERE = Path(__file__).resolve().parent
CMS = Path("/opt/homebrew/bin/cryptominisat5")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "pair_solver_protocol_v2.json").read_text())
    paths = {"script": Path(__file__), "formula": HERE / "pair_pinned.xcnf",
             "preflight": HERE / "pair_preflight_result.json", "solver": CMS.resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    cmd = [str(CMS), "--threads=1", "--maxtime=60", "--zero-exit-status",
           "--verb=1", "--printsol=1", str(paths["formula"])]
    start = time.monotonic_ns()
    out_path, err_path = HERE / "pair_solver.stdout.txt", HERE / "pair_solver.stderr.txt"
    peak_sampled = 0
    stop_reason = None
    with out_path.open("x") as out, err_path.open("x") as err:
        process = subprocess.Popen(cmd, stdout=out, stderr=err)
        observed = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak_sampled = max(peak_sampled, observed.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if peak_sampled > protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
                process.kill()
                break
            if time.monotonic_ns()-start > protocol["parent_wall_cap_seconds"]*1_000_000_000:
                stop_reason = "PARENT_TIMEOUT"
                process.kill()
                break
            time.sleep(0.02)
        exit_code = process.wait()
    wall_ns = time.monotonic_ns() - start
    stdout, stderr = out_path.read_text(), err_path.read_text()
    status = stop_reason or ("SAT_MODEL_UNAUDITED" if "s SATISFIABLE" in stdout else (
        "UNSAT" if "s UNSATISFIABLE" in stdout else "BOUNDED_UNKNOWN"))
    peak = max(peak_sampled, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    result = {"status": status, "exit_code": exit_code,
              "command": cmd, "wall_ns": wall_ns, "peak_child_rss_bytes": peak,
              "peak_sampled_rss_bytes": peak_sampled,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "stdout_sha256": digest(HERE / "pair_solver.stdout.txt"),
              "stderr_sha256": digest(HERE / "pair_solver.stderr.txt"),
              "protocol_sha256": digest(HERE / "pair_solver_protocol_v2.json")}
    with (HERE / "pair_solver_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "exit_code": exit_code,
                      "wall_ns": wall_ns, "peak_child_rss_bytes": peak}))


if __name__ == "__main__":
    main()
