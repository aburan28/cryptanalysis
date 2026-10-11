"""Run the frozen one-worker split-quartic native scan with exact receipts."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "native_protocol.json").read_text())
    for name, (path, expected) in protocol["source_sha256"].items():
        assert sha(Path(path)) == expected, name
    input_path = Path(protocol["source_sha256"]["input"][0])
    result_path = HERE / "split_n131_positive.json"
    args = [str(HERE / "native_split"), str(input_path), str(result_path),
            str(protocol["query_cap_seconds"]), str(protocol["rss_cap_bytes"])]
    started = time.monotonic()
    terminal = "EXITED"
    try:
        process = subprocess.run(args, text=True, capture_output=True,
                                 timeout=protocol["parent_cap_seconds"], check=False)
        stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        terminal = "PARENT_TIMEOUT"
        stdout = (error.stdout or b"").decode(errors="replace")
        stderr = (error.stderr or b"").decode(errors="replace")
        exit_code = None
    wall = time.monotonic() - started
    with (HERE / "split_stdout.txt").open("x") as out:
        out.write(stdout)
    with (HERE / "split_stderr.txt").open("x") as out:
        out.write(stderr)
    native = json.loads(result_path.read_text()) if result_path.exists() else None
    receipt = {"status": terminal, "exit_code": exit_code,
               "protocol_sha256": sha(HERE / "native_protocol.json"),
               "parent_wall_seconds": wall,
               "stdout_sha256": sha(HERE / "split_stdout.txt"),
               "stderr_sha256": sha(HERE / "split_stderr.txt"),
               "native_result_sha256": sha(result_path) if native else None,
               "native_status": native["status"] if native else None,
               "processed_product_states": native["processed_product_states"] if native else None,
               "query_ns": native["query_ns"] if native else None,
               "peak_rss_bytes": native["peak_rss_bytes"] if native else None}
    with (HERE / "split_receipt.json").open("x") as out:
        json.dump(receipt, out, sort_keys=True, indent=2)
        out.write("\n")
    print(json.dumps(receipt, sort_keys=True))
    if exit_code != 0 or not native or native["status"] != "COMPLETE_FACTORED_SCAN":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
