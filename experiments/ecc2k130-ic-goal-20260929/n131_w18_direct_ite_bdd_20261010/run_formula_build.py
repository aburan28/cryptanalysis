"""Build both frozen W18 direct-ITE XCNFs under parent resource limits."""

import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

import psutil


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "formula_build_run_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "builder": HERE / "build_formula.py",
             "formula_protocol": HERE / "formula_protocol.json",
             "python": Path(sys.executable).resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    runs = []
    for mode in ("constructed", "ordinary"):
        cmd = [str(paths["python"]), str(paths["builder"]), "--mode", mode]
        out_path = HERE / ("ite_%s_build.stdout.txt" % mode)
        err_path = HERE / ("ite_%s_build.stderr.txt" % mode)
        start = time.monotonic_ns()
        sampled = 0
        stop_reason = None
        with out_path.open("x") as out, err_path.open("x") as err:
            process = subprocess.Popen(cmd, stdout=out, stderr=err)
            observed = psutil.Process(process.pid)
            while process.poll() is None:
                try:
                    sampled = max(sampled, observed.memory_info().rss)
                except psutil.NoSuchProcess:
                    break
                if sampled > protocol["rss_cap_bytes"]:
                    stop_reason = "RSS_CAP"
                    process.kill()
                    break
                if time.monotonic_ns() - start > protocol["wall_cap_seconds"] * 1_000_000_000:
                    stop_reason = "PARENT_TIMEOUT"
                    process.kill()
                    break
                time.sleep(0.05)
            exit_code = process.wait()
        build_path = HERE / ("ite_%s_build.json" % mode)
        status = stop_reason or ("COMPLETE" if exit_code == 0 and build_path.exists()
                                 else "PRODUCER_FAILURE")
        run = {"mode": mode, "status": status, "command": cmd,
               "exit_code": exit_code, "wall_ns": time.monotonic_ns()-start,
               "peak_sampled_rss_bytes": sampled,
               "stdout_sha256": digest(out_path), "stderr_sha256": digest(err_path),
               "build_sha256": digest(build_path) if build_path.exists() else None}
        runs.append(run)
        if status != "COMPLETE":
            break
    result = {"status": "COMPLETE" if len(runs) == 2 and all(
                  run["status"] == "COMPLETE" for run in runs) else "PRODUCER_FAILURE",
              "runs": runs,
              "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "formula_build_run_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": result["status"],
                      "runs": [{"mode": run["mode"], "status": run["status"],
                                "wall_ns": run["wall_ns"],
                                "peak_sampled_rss_bytes": run["peak_sampled_rss_bytes"]}
                               for run in runs],
                      "stdout": [(HERE / ("ite_%s_build.stdout.txt" %
                                          run["mode"])).read_text()[-1000:]
                                 for run in runs],
                      "stderr": [(HERE / ("ite_%s_build.stderr.txt" %
                                          run["mode"])).read_text()[-1000:]
                                 for run in runs]}))


if __name__ == "__main__":
    main()
