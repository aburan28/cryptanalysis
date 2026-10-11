"""Paired exact W18 selected-seed queries with archived and linear half-traces."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w18_ondemand_seedjoin_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    files = {"runner": HERE / "run.py", "candidate_source": HERE / "native.cpp",
             "candidate_binary": HERE / "native", "baseline_source": OLD / "native.cpp",
             "baseline_binary": OLD / "native", "inherited_base": BASE / "n131_w18_seedwise_hashjoin_20261011/base.hpp",
             "archived_field": BASE / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp",
             "support": SUPPORT, "baseline_protocol": OLD / "protocol.json",
             "baseline_receipt": OLD / "run_receipt.json", "baseline_validation": OLD / "validation.json"}
    assert protocol["status"] == "frozen"
    assert protocol["source_sha256"] == {name: digest(path) for name, path in files.items()}
    assert not (HERE / "run_receipt.json").exists()
    receipt = {"status": "RUNNING", "protocol_sha256": digest(HERE / "protocol.json"),
               "cases": []}
    (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    for case_index, case in enumerate(protocol["cases"]):
        for variant in case["order"]:
            stem = f"{case_index:03d}_{variant}"
            output = HERE / f"query_{stem}.json"
            table = HERE / f"table_{stem}.tsv"
            stdout_path = HERE / f"stdout_{stem}.txt"
            stderr_path = HERE / f"stderr_{stem}.txt"
            binary = OLD / "native" if variant == "baseline" else HERE / "native"
            command = [str(binary), str(SUPPORT), str(case["seed_mask"]),
                       str(case["output_z"]), str(output),
                       str(protocol["native_cap_seconds"]), str(table)]
            started = time.perf_counter_ns()
            with stdout_path.open("x") as stdout, stderr_path.open("x") as stderr:
                try:
                    process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                             timeout=protocol["parent_cap_seconds"])
                    status = "COMPLETE" if process.returncode == 0 else "PRODUCER_FAILURE"
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    status, code = "CENSORED_TIME", None
            raw = json.loads(output.read_text()) if output.exists() else None
            row = {"name": case["name"], "case_index": case_index, "variant": variant,
                   "status": status, "returncode": code,
                   "parent_wall_ns_exploratory": time.perf_counter_ns() - started,
                   "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                   "output_sha256": digest(output) if output.exists() else None,
                   "table_sha256": digest(table) if table.exists() else None,
                   "stdout_sha256": digest(stdout_path), "stderr_sha256": digest(stderr_path),
                   "native_result": raw}
            receipt["cases"].append(row)
            (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
            print(json.dumps({"name": case["name"], "variant": variant,
                              "status": status, "build_ns": raw and raw.get("table_build_ns_exploratory"),
                              "lookup_ns": raw and raw.get("lookup_ns_exploratory")}), flush=True)
            if status != "COMPLETE":
                receipt["status"] = "INCOMPLETE"
                (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
                return
    receipt["status"] = "COMPLETE"
    (HERE / "run_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
