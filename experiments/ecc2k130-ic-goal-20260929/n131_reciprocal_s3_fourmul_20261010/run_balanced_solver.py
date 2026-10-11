"""Run a frozen balanced four-product S3 formula under wall and RSS caps."""

import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("constructed", "ordinary"), required=True)
    args = parser.parse_args()
    protocol_path = HERE / ("balanced_%s_solver_protocol.json" % args.mode)
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__),
             "formula": HERE / ("balanced_%s.xcnf" % args.mode),
             "build": HERE / ("balanced_%s_build.json" % args.mode),
             "solver": CMS.resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    cmd = [str(CMS), "--threads=1",
           "--maxtime=%d" % protocol["solver_wall_cap_seconds"],
           "--zero-exit-status", "--verb=1", "--printsol=1", str(paths["formula"])]
    out_path = HERE / ("balanced_%s_solver.stdout.txt" % args.mode)
    err_path = HERE / ("balanced_%s_solver.stderr.txt" % args.mode)
    start = time.monotonic_ns()
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
            if time.monotonic_ns() - start > protocol["parent_wall_cap_seconds"] * 1_000_000_000:
                stop_reason = "PARENT_TIMEOUT"
                process.kill()
                break
            time.sleep(0.05)
        exit_code = process.wait()
    wall_ns = time.monotonic_ns() - start
    stdout = out_path.read_text()
    status = stop_reason or ("SAT_MODEL_UNAUDITED" if "s SATISFIABLE" in stdout else
                             "UNSAT" if "s UNSATISFIABLE" in stdout else
                             "BOUNDED_UNKNOWN")
    result = {"status": status, "mode": args.mode, "exit_code": exit_code,
              "command": cmd, "wall_ns": wall_ns,
              "peak_child_rss_bytes": max(peak_sampled,
                                          resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
              "peak_sampled_rss_bytes": peak_sampled,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "stdout_sha256": digest(out_path), "stderr_sha256": digest(err_path),
              "protocol_sha256": digest(protocol_path)}
    with (HERE / ("balanced_%s_solver_result.json" % args.mode)).open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "exit_code": exit_code,
                      "wall_ns": wall_ns,
                      "peak_child_rss_bytes": result["peak_child_rss_bytes"]}))


if __name__ == "__main__":
    main()
