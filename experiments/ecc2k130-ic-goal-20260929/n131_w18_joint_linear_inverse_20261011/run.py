"""Freeze and execute the exact joint-linear W18 inverse panel."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
OLD = BASE / "n131_w18_allseed_linear_query_20261011"
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
FIELD = BASE / "n131_w14_coupled_fouratom_inverse_20261010"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write("\n")


def sources():
    return {
        "native_source": HERE / "native.cpp",
        "native_binary": HERE / "native",
        "runner": HERE / "run.py",
        "support": SUPPORT,
        "field_source": FIELD / "native.cpp",
        "field_terms": FIELD / "resultant_terms.hpp",
        "prior_protocol": OLD / "protocol.json",
        "prior_audit": OLD / "terminal_audit.json",
    }


def freeze():
    prior = json.loads((OLD / "protocol.json").read_text())
    assert len(prior["cases"]) == 4 and prior["seed_count"] == 262143
    new_json(HERE / "protocol.json", {
        "status": "FROZEN_BEFORE_QUERY",
        "curve_id": prior["curve_id"],
        "candidate_id": None,
        "cases": prior["cases"],
        "input_law": "two archived true raw pair outputs, one published-point raw coordinate, and one trace-one field control",
        "algorithm": "131-row binary solve of 18 seed-square and 35 product columns; exact all-seed fallback on consistent rank deficiency",
        "query_boundary": "supplied coordinate through unrotation, joint solve, exact inverse/source checks, and any fallback; result serialization, source loading, and fixed basis construction excluded",
        "workers": 1,
        "query_cap_seconds": 120,
        "parent_cap_seconds": 150,
        "rss_cap_bytes": 4 * 1024**3,
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    })


def run():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    for index, case in enumerate(protocol["cases"]):
        prefix = f"case_{index:03d}"
        output = HERE / f"{prefix}.json"
        stdout = HERE / f"{prefix}.stdout.txt"
        stderr = HERE / f"{prefix}.stderr.txt"
        assert not any(path.exists() for path in (output, stdout, stderr))
        command = [str(HERE / "native"), str(SUPPORT), str(case["coordinate"]),
                   str(case["rotation"]), str(output), str(protocol["query_cap_seconds"])]
        start = time.perf_counter_ns()
        with stdout.open("x") as out, stderr.open("x") as err:
            try:
                returncode = subprocess.run(command, cwd=HERE, stdout=out, stderr=err,
                                            timeout=protocol["parent_cap_seconds"]).returncode
            except subprocess.TimeoutExpired:
                returncode = None
        parent_ns = time.perf_counter_ns() - start
        result = json.loads(output.read_text()) if output.exists() else None
        status = ("COMPLETE" if result and returncode == 0 and result["status"] == "COMPLETE"
                  else "CENSORED_PARENT_TIME" if returncode is None else "PRODUCER_FAILURE")
        new_json(HERE / f"{prefix}.receipt.json", {
            "status": status, "name": case["name"], "returncode": returncode,
            "parent_wall_ns_exploratory": parent_ns,
            "protocol_sha256": sha(protocol_path),
            "output_sha256": sha(output) if output.exists() else None,
            "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
        })
        if status != "COMPLETE":
            print(prefix, status, flush=True)
            return
        old = json.loads((OLD / f"case_{index:03d}_target_linear.json").read_text())
        same = result["hits"] == old["hits"] and result["unrotated_reciprocal"] == old["unrotated_reciprocal"]
        new_json(HERE / f"{prefix}.comparison.json", {
            "status": "PASS_EXACT_HIT_MATCH" if same else "FAIL_HIT_MATCH",
            "name": case["name"], "joint_rank": result["joint_rank"],
            "joint_consistent": result["joint_consistent"], "fallback": result["fallback"],
            "new_query_ns_exploratory": result["query_ns_exploratory"],
            "old_query_ns_exploratory": old["query_ns_exploratory"],
            "new_rss_bytes": result["peak_rss_bytes"],
            "old_rss_bytes": old["peak_rss_bytes"],
        })
        assert same
        print(prefix, "PASS", "rank", result["joint_rank"], "query_ns",
              result["query_ns_exploratory"], flush=True)


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
