"""Execute the frozen W20 FWHT count under parent resource limits."""

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
    protocol_path = HERE / "count_run_protocol_v2.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "count": HERE / "count_pairs_v2.py",
             "count_protocol": HERE / "count_protocol_v2.json",
             "prior_failure": HERE / "count_run_result.json",
             "python": Path(sys.executable).resolve()}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    cmd = [str(paths["python"]), str(paths["count"])]
    out_path = HERE / "count_v2.stdout.txt"
    err_path = HERE / "count_v2.stderr.txt"
    start = time.monotonic_ns()
    peak = 0
    stop_reason = None
    with out_path.open("x") as out, err_path.open("x") as err:
        process = subprocess.Popen(cmd, stdout=out, stderr=err)
        observed = psutil.Process(process.pid)
        while process.poll() is None:
            try:
                peak = max(peak, observed.memory_info().rss)
            except psutil.NoSuchProcess:
                break
            if peak > protocol["rss_cap_bytes"]:
                stop_reason = "RSS_CAP"
                process.kill()
                break
            if time.monotonic_ns() - start > protocol["wall_cap_seconds"] * 1_000_000_000:
                stop_reason = "PARENT_TIMEOUT"
                process.kill()
                break
            time.sleep(0.05)
        exit_code = process.wait()
    output = HERE / "count_result_v2.json"
    status = stop_reason or ("COMPLETE" if exit_code == 0 and output.exists()
                             else "PRODUCER_FAILURE")
    result = {"status": status, "command": cmd, "exit_code": exit_code,
              "wall_ns": time.monotonic_ns() - start,
              "peak_child_rss_bytes": max(peak,
                                          resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "stdout_sha256": digest(out_path), "stderr_sha256": digest(err_path),
              "count_result_sha256": digest(output) if output.exists() else None,
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "count_run_result_v2.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status,
                      "wall_ns": result["wall_ns"],
                      "peak_child_rss_bytes": result["peak_child_rss_bytes"],
                      "producer_stdout": out_path.read_text()[-1000:],
                      "producer_stderr": err_path.read_text()[-1000:]}))


if __name__ == "__main__":
    main()
