"""Run the frozen native prefix subtraction and save its resource receipt."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
INPUT = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"
ROWS = BASE / "n41_w6_public_seed_predictor_20261011/rows.tsv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "extract_protocol_v2.json").read_text())
    files = {"extractor": HERE / "extract.cpp", "binary": HERE / "extract",
             "runner": HERE / "extract_run.py", "source_input": INPUT,
             "source_rows": ROWS,
             "source_generator": BASE / "n41_w6_public_seed_predictor_20261011/generate.cpp"}
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"] == {name: digest(path) for name, path in files.items()}
    assert not (HERE / "residuals.tsv").exists()
    command = [str(HERE / "extract"), str(INPUT), str(ROWS), str(HERE / "residuals.tsv")]
    start = time.perf_counter_ns()
    with (HERE / "extract_v2.stdout.txt").open("x") as stdout, \
         (HERE / "extract_v2.stderr.txt").open("x") as stderr:
        try:
            proc = subprocess.run(command, stdout=stdout, stderr=stderr,
                                  timeout=protocol["parent_cap_seconds"], check=False)
            status = "COMPLETE" if proc.returncode == 0 else "PRODUCER_FAILURE"
            code = proc.returncode
        except subprocess.TimeoutExpired:
            status, code = "CENSORED_TIME", None
    elapsed = time.perf_counter_ns() - start
    receipt = {"status": status, "returncode": code,
               "protocol_sha256": digest(HERE / "extract_protocol_v2.json"),
               "source_sha256": protocol["source_sha256"],
               "wall_ns_exploratory": elapsed,
               "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               "residual_sha256": digest(HERE / "residuals.tsv")
               if (HERE / "residuals.tsv").exists() else None,
               "stdout_sha256": digest(HERE / "extract_v2.stdout.txt"),
               "stderr_sha256": digest(HERE / "extract_v2.stderr.txt")}
    with (HERE / "extract_receipt_v2.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": status, "wall_seconds": elapsed / 1e9,
                      "peak_child_rss_bytes": receipt["peak_child_rss_bytes"]}))


if __name__ == "__main__":
    main()
