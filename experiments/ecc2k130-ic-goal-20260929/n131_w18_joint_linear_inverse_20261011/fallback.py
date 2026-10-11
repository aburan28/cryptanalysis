"""Compare a consistent lower-rank coordinate with the all-seed reference."""

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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


def freeze():
    new_json(HERE / "fallback_protocol.json", {
        "status": "FROZEN_BEFORE_QUERY",
        "coordinates": [2, 4], "rotation": 0,
        "input_law": "field monomials t and t^2; their squares lie in the seed-square span, giving consistent low-rank linear systems",
        "query_cap_seconds": 120, "parent_cap_seconds": 150,
        "rss_cap_bytes": 4 * 1024**3, "workers": 1,
        "source_sha256": {"runner": sha(HERE / "fallback.py"),
                          "native_source": sha(HERE / "native.cpp"),
                          "native_binary": sha(HERE / "native"),
                          "old_source": sha(OLD / "native.cpp"),
                          "old_binary": sha(OLD / "native"),
                          "support": sha(SUPPORT)},
    })


def run():
    protocol = json.loads((HERE / "fallback_protocol.json").read_text())
    assert protocol["source_sha256"] == {
        "runner": sha(HERE / "fallback.py"), "native_source": sha(HERE / "native.cpp"),
        "native_binary": sha(HERE / "native"), "old_source": sha(OLD / "native.cpp"),
        "old_binary": sha(OLD / "native"), "support": sha(SUPPORT)}
    for index, coordinate in enumerate(protocol["coordinates"]):
        rows = {}
        for arm, binary in (("old", OLD / "native"), ("joint", HERE / "native")):
            output = HERE / f"fallback_{index:03d}_{arm}.json"
            stdout = HERE / f"fallback_{index:03d}_{arm}.stdout.txt"
            stderr = HERE / f"fallback_{index:03d}_{arm}.stderr.txt"
            assert not any(path.exists() for path in (output, stdout, stderr))
            command = [str(binary), str(SUPPORT), str(coordinate), "0", str(output),
                       str(protocol["query_cap_seconds"])]
            start = time.perf_counter_ns()
            with stdout.open("x") as out, stderr.open("x") as err:
                try:
                    code = subprocess.run(command, stdout=out, stderr=err,
                                          cwd=HERE, timeout=protocol["parent_cap_seconds"]).returncode
                except subprocess.TimeoutExpired:
                    code = None
            parent_ns = time.perf_counter_ns()-start
            row = json.loads(output.read_text()) if output.exists() else None
            new_json(HERE / f"fallback_{index:03d}_{arm}.receipt.json", {
                "returncode": code, "parent_wall_ns_exploratory": parent_ns,
                "status": row["status"] if row else "NO_OUTPUT",
                "output_sha256": sha(output) if output.exists() else None,
                "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
            })
            if code != 0 or row is None or row["status"] != "COMPLETE":
                print(index, arm, "INCOMPLETE", flush=True)
                return
            rows[arm] = row
        assert rows["joint"]["fallback"] and rows["joint"]["joint_consistent"]
        assert rows["joint"]["joint_rank"] < 53
        same = rows["joint"]["hits"] == rows["old"]["hits"]
        new_json(HERE / f"fallback_{index:03d}.comparison.json", {
            "status": "PASS_EXACT_HIT_MATCH" if same else "FAIL_HIT_MATCH",
            "coordinate": coordinate, "joint_rank": rows["joint"]["joint_rank"],
            "old_hits": len(rows["old"]["hits"]), "joint_hits": len(rows["joint"]["hits"]),
            "old_query_ns_exploratory": rows["old"]["query_ns_exploratory"],
            "joint_query_ns_exploratory": rows["joint"]["query_ns_exploratory"],
        })
        assert same
        print(index, "PASS rank", rows["joint"]["joint_rank"], flush=True)


if __name__ == "__main__":
    assert sys.argv[1:] in (["freeze"], ["run"])
    freeze() if sys.argv[1] == "freeze" else run()
