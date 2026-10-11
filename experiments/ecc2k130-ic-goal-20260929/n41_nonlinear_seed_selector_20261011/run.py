"""Execute one frozen, held-out nonlinear N41 seed-selector experiment."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n41_w6_public_seed_predictor_20261011"
RESIDUAL = BASE / "n41_prefix_residual_seed_selector_20261011"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    files = {"source": HERE / "forest.cpp", "binary": HERE / "forest",
             "runner": HERE / "run.py", "residual_rows": RESIDUAL / "residuals.tsv",
             "residual_protocol": RESIDUAL / "extract_protocol_v2.json",
             "residual_receipt": RESIDUAL / "extract_receipt_v2.json",
             "prior_result": PRIOR / "fit_result.json",
             "prior_audit": PRIOR / "terminal_audit.json"}
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"] == {key: digest(path) for key, path in files.items()}
    assert not (HERE / "run_receipt.json").exists()
    command = [str(HERE / "forest"), str(RESIDUAL / "residuals.tsv"),
               str(HERE / "predictions.tsv")]
    started = time.perf_counter_ns()
    with (HERE / "stdout.txt").open("x") as stdout, (HERE / "stderr.txt").open("x") as stderr:
        try:
            process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                     timeout=protocol["parent_cap_seconds"])
            status = "COMPLETE" if process.returncode == 0 else "PRODUCER_FAILURE"
            code = process.returncode
        except subprocess.TimeoutExpired:
            status, code = "CENSORED_TIME", None
    receipt = {"status": status, "returncode": code,
               "protocol_sha256": digest(HERE / "protocol.json"),
               "parent_wall_ns_exploratory": time.perf_counter_ns() - started,
               "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               "predictions_sha256": digest(HERE / "predictions.tsv")
               if (HERE / "predictions.tsv").exists() else None,
               "stdout_sha256": digest(HERE / "stdout.txt"),
               "stderr_sha256": digest(HERE / "stderr.txt")}
    (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
