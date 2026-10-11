"""Run the frozen product-span inverse panel with four paired all-seed controls."""

import hashlib
import json
import resource
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w18_allseed_pair_inverse_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files():
    return {"runner": HERE / "run.py", "candidate_source": HERE / "native.cpp",
            "candidate_binary": HERE / "native", "inherited_base": BASE / "n131_w18_seedwise_hashjoin_20261011/base.hpp",
            "inherited_field": BASE / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp",
            "baseline_source": OLD / "native.cpp", "baseline_binary": OLD / "native",
            "baseline_protocol": OLD / "protocol.json", "baseline_validation": OLD / "sample_validation.json",
            "support": SUPPORT, "panel": HERE / "panel.json",
            "prepare_protocol": HERE / "prepare_protocol.json", "prepare_source": HERE / "prepare.py"}


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    panel = json.loads((HERE / "panel.json").read_text())
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"] == {name: digest(path) for name, path in source_files().items()}
    assert len(panel["cases"]) == 196
    assert not (HERE / "run_receipt.json").exists()
    assert not (HERE / "results.jsonl").exists()
    receipt = {"status": "RUNNING", "protocol_sha256": digest(HERE / "protocol.json"),
               "case_count": len(panel["cases"]), "completed_executions": 0,
               "baseline_executions": 0, "candidate_executions": 0,
               "results_sha256": None}
    (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="ecc2k-span-query-", dir="/private/tmp") as temp:
        result_path = Path(temp) / "result.json"
        with (HERE / "results.jsonl").open("x") as records:
            for case_index, case in enumerate(panel["cases"]):
                variants = ["baseline", "candidate"] if case_index % 2 == 0 else ["candidate", "baseline"]
                if case_index >= 4:
                    variants = ["candidate"]
                for variant in variants:
                    binary = OLD / "native" if variant == "baseline" else HERE / "native"
                    command = [str(binary), str(SUPPORT), str(case["coordinate"]),
                               str(case["rotation"]), str(result_path),
                               str(protocol["native_cap_seconds"])]
                    assert not result_path.exists()
                    start = time.perf_counter_ns()
                    try:
                        process = subprocess.run(command, capture_output=True, text=True,
                                                 timeout=protocol["parent_cap_seconds"])
                        status = "COMPLETE" if process.returncode == 0 else "PRODUCER_FAILURE"
                        code = process.returncode
                        stdout, stderr = process.stdout, process.stderr
                    except subprocess.TimeoutExpired as error:
                        status, code = "CENSORED_TIME", None
                        stdout = (error.stdout or b"").decode(errors="replace")
                        stderr = (error.stderr or b"").decode(errors="replace")
                    raw = json.loads(result_path.read_text()) if result_path.exists() else None
                    row = {"case_index": case_index, "name": case["name"], "variant": variant,
                           "status": status, "returncode": code,
                           "parent_wall_ns_exploratory": time.perf_counter_ns() - start,
                           "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                           "stdout": stdout, "stderr": stderr,
                           "native_result_sha256": digest(result_path) if raw is not None else None,
                           "native_result": raw}
                    records.write(json.dumps(row, sort_keys=True) + "\n")
                    records.flush()
                    if result_path.exists():
                        result_path.unlink()
                    receipt["completed_executions"] += 1
                    receipt[f"{variant}_executions"] += 1
                    if status != "COMPLETE":
                        receipt["status"] = "INCOMPLETE"
                        receipt["results_sha256"] = digest(HERE / "results.jsonl")
                        (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
                        print(json.dumps({"case": case_index, "variant": variant, "status": status}), flush=True)
                        return
                if case_index < 4 or case_index % 32 == 31:
                    print(json.dumps({"completed_cases": case_index + 1,
                                      "completed_executions": receipt["completed_executions"]}), flush=True)
    receipt["status"] = "COMPLETE"
    receipt["results_sha256"] = digest(HERE / "results.jsonl")
    (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
