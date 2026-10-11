"""Resume the frozen paired run after the 2026-10-11 ENOSPC interruption."""

import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
OLD = run.OLD
SUPPORT = run.SUPPORT


def save_atomic(path, value):
    staging = path.with_suffix(path.suffix + ".tmp")
    staging.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    staging.replace(path)


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    receipt_path = HERE / "run_receipt.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "RUNNING"
    assert receipt["protocol_sha256"] == run.digest(HERE / "protocol.json")
    assert [(row["case_index"], row["variant"]) for row in receipt["cases"]] == [
        (0, "baseline"), (0, "linear"), (1, "linear"), (1, "baseline")]
    files = {"runner": HERE / "run.py", "candidate_source": HERE / "native.cpp",
             "candidate_binary": HERE / "native", "baseline_source": OLD / "native.cpp",
             "baseline_binary": OLD / "native", "inherited_base": HERE.parent / "n131_w18_seedwise_hashjoin_20261011/base.hpp",
             "archived_field": HERE.parent / "n131_w14_coupled_fouratom_inverse_20261010/native.cpp",
             "support": SUPPORT, "baseline_protocol": OLD / "protocol.json",
             "baseline_receipt": OLD / "run_receipt.json", "baseline_validation": OLD / "validation.json"}
    assert protocol["source_sha256"] == {name: run.digest(path) for name, path in files.items()}
    case = protocol["cases"][2]
    for variant in case["order"]:
        stem = f"002_{variant}"
        output = HERE / f"query_{stem}.json"
        table = HERE / f"table_{stem}.tsv"
        stdout_path = HERE / f"stdout_{stem}.txt"
        stderr_path = HERE / f"stderr_{stem}.txt"
        assert not any(path.exists() for path in (output, table, stdout_path, stderr_path))
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
        row = {"name": case["name"], "case_index": 2, "variant": variant,
               "status": status, "returncode": code,
               "parent_wall_ns_exploratory": time.perf_counter_ns() - started,
               "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
               "output_sha256": run.digest(output) if output.exists() else None,
               "table_sha256": run.digest(table) if table.exists() else None,
               "stdout_sha256": run.digest(stdout_path), "stderr_sha256": run.digest(stderr_path),
               "native_result": raw}
        receipt["cases"].append(row)
        receipt["resume_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if status != "COMPLETE":
            receipt["status"] = "INCOMPLETE"
        save_atomic(receipt_path, receipt)
        print(json.dumps({"name": case["name"], "variant": variant,
                          "status": status, "build_ns": raw and raw.get("table_build_ns_exploratory"),
                          "lookup_ns": raw and raw.get("lookup_ns_exploratory")}), flush=True)
        if status != "COMPLETE":
            return
        assert row["table_sha256"] == run.digest(OLD / "table_002.tsv")
        table.unlink()  # The exact checked-Sage archive retains the matching table.
    receipt["status"] = "COMPLETE"
    save_atomic(receipt_path, receipt)


if __name__ == "__main__":
    main()
