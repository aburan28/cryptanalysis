"""Run frozen N41/N131 product-translation XOR correlations."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORTS = {
    "n41": HERE / "support_n41.tsv",
    "n131": BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "frozen"
    files = {"producer": HERE / "run.py", "census_source": HERE / "census.cpp",
             "census_binary": HERE / "census", "exporter": HERE / "export_n41.py",
             "n41_source_input": BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt",
             "n41_support": SUPPORTS["n41"], "n131_support": SUPPORTS["n131"]}
    assert protocol["source_sha256"] == {name: digest(path) for name, path in files.items()}
    receipt = {"status": "RUNNING", "protocol_sha256": digest(HERE / "protocol.json"),
               "cases": []}
    with (HERE / "receipt.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    for name, dimension in (("n41", 6), ("n131", 18)):
        output = HERE / f"per_seed_{name}.tsv"
        stdout_path = HERE / f"{name}.stdout.txt"
        stderr_path = HERE / f"{name}.stderr.txt"
        command = [str(HERE / "census"), str(dimension), str(SUPPORTS[name]), str(output)]
        started = time.perf_counter_ns()
        with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
            try:
                process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                         timeout=protocol["parent_cap_seconds_per_case"])
                status = "COMPLETE" if process.returncode == 0 else "PRODUCER_FAILURE"
                code = process.returncode
            except subprocess.TimeoutExpired:
                status, code = "CENSORED_TIME", None
        row = {"name": name, "dimension": dimension, "status": status,
               "returncode": code, "wall_ns_exploratory": time.perf_counter_ns() - started,
               "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               "output_sha256": digest(output) if output.exists() else None,
               "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path)}
        receipt["cases"].append(row)
        (HERE / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"name": name, "status": status,
                          "seconds": row["wall_ns_exploratory"] / 1e9}), flush=True)
        if status != "COMPLETE":
            break
    receipt["status"] = "COMPLETE" if len(receipt["cases"]) == 2 and all(
        row["status"] == "COMPLETE" for row in receipt["cases"]) else "INCOMPLETE"
    (HERE / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
