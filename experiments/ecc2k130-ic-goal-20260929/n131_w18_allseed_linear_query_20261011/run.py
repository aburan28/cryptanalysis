"""Freeze and pair the W18 all-seed target-linear query with its reference."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
PRIOR = BASE / "n131_w18_allseed_pair_inverse_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
ARCH = BASE / "n131_w14_coupled_fouratom_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {"generator": HERE / "generate.py", "runner": HERE / "run.py",
            "linear_source": HERE / "native.cpp", "linear_binary": HERE / "native",
            "prior_source": PRIOR / "native.cpp", "prior_binary": PRIOR / "native",
            "prior_protocol": PRIOR / "protocol.json", "prior_audit": PRIOR / "terminal_audit.json",
            "support": SUPPORT, "field_source": ARCH / "native.cpp",
            "field_terms": ARCH / "resultant_terms.hpp"}


def freeze():
    assert not (HERE / "protocol.json").exists()
    prior = json.loads((PRIOR / "protocol.json").read_text())
    assert prior["seed_count"] == 262143 and len(prior["cases"]) == 4
    protocol = {
        "status": "FROZEN_BEFORE_PAIRED_QUERY",
        "curve_id": prior["curve_id"], "candidate_id": None,
        "cases": prior["cases"], "seed_count": 262143,
        "arms": ["reference", "target_linear"],
        "case_arm_order": [["reference", "target_linear"],
                           ["target_linear", "reference"],
                           ["reference", "target_linear"],
                           ["target_linear", "reference"]],
        "workers": 1, "per_run_query_cap_seconds": 120,
        "per_run_parent_cap_seconds": 180,
        "rss_cap_bytes": 4 * 1024**3,
        "candidate_product_field_multiplies": {
            "reference_trace_zero": 2 * 262143,
            "target_linear_trace_zero": 19,
            "either_trace_one": 0,
        },
        "query_boundary": "supplied coordinate through unrotation, halftrace, all-seed candidate-product formation, image/source tests, and completed output; reusable map construction excluded",
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    write_new(HERE / "protocol.json", protocol)
    print("frozen", len(protocol["cases"]), "cases")


def semantic(result):
    return {key: value for key, value in result.items()
            if key not in ("setup_ns_exploratory", "query_ns_exploratory", "peak_rss_bytes")}


def run():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["status"] == "FROZEN_BEFORE_PAIRED_QUERY"
    for index, (case, order) in enumerate(zip(protocol["cases"], protocol["case_arm_order"])):
        results = {}
        for arm in order:
            prefix = f"case_{index:03d}_{arm}"
            output = HERE / f"{prefix}.json"
            stdout = HERE / f"{prefix}.stdout.txt"
            stderr = HERE / f"{prefix}.stderr.txt"
            assert not any(path.exists() for path in (output, stdout, stderr))
            executable = PRIOR / "native" if arm == "reference" else HERE / "native"
            command = [str(executable), str(SUPPORT), str(case["coordinate"]),
                       str(case["rotation"]), str(output),
                       str(protocol["per_run_query_cap_seconds"])]
            started = time.perf_counter_ns()
            with stdout.open("x") as out, stderr.open("x") as err:
                try:
                    process = subprocess.run(command, cwd=HERE, stdout=out, stderr=err,
                                             timeout=protocol["per_run_parent_cap_seconds"])
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    returncode = None
            parent_ns = time.perf_counter_ns() - started
            result = json.loads(output.read_text()) if output.exists() else None
            status = ("COMPLETE" if returncode == 0 and result is not None and
                      result["status"] == "COMPLETE" else
                      "CENSORED_PARENT_TIME" if returncode is None else "PRODUCER_FAILURE")
            if status == "COMPLETE":
                assert result["seed_count"] == protocol["seed_count"]
                assert result["seeds_checked"] == (0 if result["trace_bit"] else protocol["seed_count"])
                assert result["peak_rss_bytes"] < protocol["rss_cap_bytes"]
                assert result["query_ns_exploratory"] < protocol["per_run_query_cap_seconds"] * 10**9
                results[arm] = result
            receipt = {"name": case["name"], "arm": arm, "status": status,
                       "returncode": returncode, "parent_wall_ns_exploratory": parent_ns,
                       "protocol_sha256": sha(protocol_path),
                       "output_sha256": sha(output) if output.exists() else None,
                       "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)}
            write_new(HERE / f"{prefix}.receipt.json", receipt)
            print(prefix, status,
                  "query_s", result["query_ns_exploratory"] / 1e9 if result else None,
                  flush=True)
            if status != "COMPLETE":
                return
        assert semantic(results["reference"]) == semantic(results["target_linear"])
        assert semantic(results["reference"]) == semantic(json.loads(
            (PRIOR / f"query_{index:03d}.json").read_text()))
        write_new(HERE / f"case_{index:03d}_comparison.json", {
            "status": "PASS_EXACT_SEMANTIC_MATCH",
            "name": case["name"], "protocol_sha256": sha(protocol_path),
            "reference_query_ns_exploratory": results["reference"]["query_ns_exploratory"],
            "target_linear_query_ns_exploratory": results["target_linear"]["query_ns_exploratory"],
            "reference_peak_rss_bytes": results["reference"]["peak_rss_bytes"],
            "target_linear_peak_rss_bytes": results["target_linear"]["peak_rss_bytes"],
        })


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
