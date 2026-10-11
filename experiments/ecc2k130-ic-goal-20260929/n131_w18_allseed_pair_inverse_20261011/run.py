"""Freeze and execute complete W18 all-seed pair-output inverse controls."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w16_w18_sixpair_width_gate_20261010/support_w18.tsv"
TABLE = BASE / "n131_w18_seedwise_fouratom_20261011/table.tsv"
OLD = BASE / "n131_w14_coupled_fouratom_inverse_20261010"
W15 = BASE / "n131_w15_allseed_inverse_20261011"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sources():
    return {
        "generator": HERE / "generate.py",
        "runner": HERE / "run.py",
        "native_source": HERE / "native.cpp",
        "native_binary": HERE / "native",
        "support": SUPPORT,
        "w18_pair_table": TABLE,
        "w15_controls": W15 / "protocol.json",
        "archived_field": OLD / "native.cpp",
        "archived_terms": OLD / "resultant_terms.hpp",
    }


def cases():
    coordinate, a, b = [int(x) for x in TABLE.open().readline().split()]
    w15 = json.loads((W15 / "protocol.json").read_text())["cases"]
    assert (a, b) == (16601, 30127)
    return [
        {"name": "w18_seed_13686_rotation_26", "coordinate": coordinate,
         "rotation": 26, "expected_pair": [a, b]},
        {"name": "w15_seed_12004_rotation_0", "coordinate": w15[0]["coordinate"],
         "rotation": 0, "expected_pair": w15[0]["expected_pair"]},
        {"name": "published_point_lift_0", "coordinate": w15[4]["coordinate"],
         "rotation": 0, "expected_pair": None},
        {"name": "trace_one_control", "coordinate": 1,
         "rotation": 0, "expected_pair": None},
    ]


def freeze():
    assert not (HERE / "protocol.json").exists()
    protocol = {
        "status": "FROZEN_BEFORE_QUERY",
        "curve_id": "EC1N131Ckb1heb5f1998f20b",
        "candidate_id": None,
        "source_width": 18,
        "seed_count": 262143,
        "source_masks": 131307,
        "cases": cases(),
        "workers": 1,
        "query_cap_seconds": 120,
        "parent_cap_seconds": 180,
        "rss_cap_bytes": 4 * 1024**3,
        "timing_boundary": "supplied pair reciprocal to complete all-seed linear-image and source filter; target-independent map setup outside query",
        "source_sha256": {name: sha(path) for name, path in sources().items()},
    }
    save_new(HERE / "protocol.json", protocol)
    print("frozen", len(protocol["cases"]), "cases")


def run():
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert protocol["source_sha256"] == {name: sha(path) for name, path in sources().items()}
    assert protocol["status"] == "FROZEN_BEFORE_QUERY"
    for index, case in enumerate(protocol["cases"]):
        output = HERE / f"query_{index:03d}.json"
        stdout = HERE / f"stdout_{index:03d}.txt"
        stderr = HERE / f"stderr_{index:03d}.txt"
        assert not any(path.exists() for path in (output, stdout, stderr))
        command = [str(HERE / "native"), str(SUPPORT), str(case["coordinate"]),
                   str(case["rotation"]), str(output),
                   str(protocol["query_cap_seconds"])]
        started = time.perf_counter_ns()
        with stdout.open("x") as out, stderr.open("x") as err:
            try:
                process = subprocess.run(command, cwd=HERE, stdout=out, stderr=err,
                                         timeout=protocol["parent_cap_seconds"])
                returncode = process.returncode
                status = "COMPLETE" if returncode == 0 else "PRODUCER_FAILURE"
            except subprocess.TimeoutExpired:
                returncode = None
                status = "CENSORED_PARENT_TIME"
        parent_ns = time.perf_counter_ns() - started
        raw = json.loads(output.read_text()) if output.exists() else None
        if status == "COMPLETE":
            assert raw["status"] == "COMPLETE"
            assert raw["peak_rss_bytes"] < protocol["rss_cap_bytes"]
            assert raw["seed_count"] == protocol["seed_count"]
            assert raw["seeds_checked"] == (0 if raw["trace_bit"] else protocol["seed_count"])
            assert raw["rotation"] == case["rotation"]
            assert len(raw["hits"]) == raw["source_pair_hits"] - raw["column_rejects"]
            if case["expected_pair"] is not None:
                assert tuple(case["expected_pair"]) in {tuple(hit["masks"]) for hit in raw["hits"]}
        receipt = {
            "status": status,
            "case": case,
            "returncode": returncode,
            "parent_wall_ns_exploratory": parent_ns,
            "protocol_sha256": sha(protocol_path),
            "native_result": raw,
            "output_sha256": sha(output) if output.exists() else None,
            "stdout_sha256": sha(stdout),
            "stderr_sha256": sha(stderr),
        }
        save_new(HERE / f"receipt_{index:03d}.json", receipt)
        print(case["name"], status,
              "hits", len(raw["hits"]) if raw else None,
              "query_s", raw["query_ns_exploratory"] / 1e9 if raw else None,
              flush=True)
        if status != "COMPLETE" or raw["status"] != "COMPLETE":
            break


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
