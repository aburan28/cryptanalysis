"""Run the frozen native W20 support exporter with wall and RSS caps."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import psutil


HERE = Path(__file__).resolve().parent
LIBRARY = HERE.parent.parent / "koblitz-s5-invariant-20260924/lowpoly_w23_geometry.cpp"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    protocol_path = HERE / "export_protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"script": Path(__file__), "source": HERE / "export_w20.cpp",
             "binary": HERE / "export_w20", "library": LIBRARY,
             "compiler_version": HERE / "compiler_version.txt"}
    for name, path in paths.items():
        assert protocol["source_sha256"][name] == digest(path), name
    assert protocol["wall_cap_seconds"] == 120
    assert protocol["rss_cap_bytes"] == 4294967296
    cmd = [str(paths["binary"].resolve()), str(HERE.resolve())]
    stdout_path = HERE / "export.stdout.txt"
    stderr_path = HERE / "export.stderr.txt"
    start = time.monotonic_ns()
    peak_sampled = 0
    stop_reason = None
    with stdout_path.open("x") as out, stderr_path.open("x") as err:
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
            if time.monotonic_ns() - start > protocol["wall_cap_seconds"] * 1_000_000_000:
                stop_reason = "PARENT_TIMEOUT"
                process.kill()
                break
            time.sleep(0.02)
        exit_code = process.wait()
    wall_ns = time.monotonic_ns() - start
    receipt_path = HERE / "export_receipt.json"
    table_path = HERE / "support_w20.tsv"
    status = stop_reason or ("COMPLETE" if exit_code == 0 and receipt_path.exists()
                             and table_path.exists() else "PRODUCER_FAILURE")
    result = {"status": status, "exit_code": exit_code, "command": cmd,
              "wall_ns": wall_ns,
              "peak_child_rss_bytes": max(peak_sampled,
                                          resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),
              "source_sha256": {name: digest(path) for name, path in paths.items()},
              "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path),
              "export_receipt_sha256": digest(receipt_path) if receipt_path.exists() else None,
              "table_sha256": digest(table_path) if table_path.exists() else None,
              "protocol_sha256": digest(protocol_path)}
    with (HERE / "export_run_result.json").open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": status, "wall_ns": wall_ns,
                      "peak_child_rss_bytes": result["peak_child_rss_bytes"],
                      "table_sha256": result["table_sha256"]}))


if __name__ == "__main__":
    main()
