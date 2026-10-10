#!/usr/bin/env python3
"""Audit Walsh support counts against all direct accepted W15 mask pairs."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w15_coupled_sixpair_20261010/support_w15.tsv"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_counts(path):
    rows = [tuple(map(int, line.split())) for line in path.read_text().splitlines()]
    assert len(rows) == 32767
    assert [seed for seed, _ in rows] == list(range(1, 32768))
    return [0] + [value for _, value in rows]


def main():
    freeze_path = HERE / "direct_protocol.json"
    freeze = json.loads(freeze_path.read_text())
    sources = {"runner": Path(__file__), "native": HERE / "direct_counts.cpp",
               "support": SUPPORT, "walsh_result": HERE / "result.json",
               "walsh_counts": HERE / "signed_seed_counts.tsv"}
    assert freeze["status"] == "FROZEN_BEFORE_DIRECT_W15_AUDIT"
    assert freeze["source_sha256"] == {name: sha(path) for name, path in sources.items()}
    assert not (HERE / "direct_audit.json").exists()
    binary = HERE / "direct_counts"
    output = HERE / "direct_seed_counts.tsv"
    assert not binary.exists() and not output.exists()
    started = time.monotonic_ns()
    command = ["clang++", "-std=c++17", "-O3", "-o", str(binary),
               str(HERE / "direct_counts.cpp")]
    subprocess.run(command, check=True, capture_output=True, text=True)
    build_ns = time.monotonic_ns()-started
    subprocess.run([str(binary), str(SUPPORT), str(output)],
                   check=True, capture_output=True, text=True)
    enumerate_ns = time.monotonic_ns()-started-build_ns
    direct = read_counts(output)
    walsh = read_counts(HERE / "signed_seed_counts.tsv")
    assert direct == walsh
    result = json.loads((HERE / "result.json").read_text())
    n = sum(direct)
    m = sum(v*v for v in direct)
    assert n == result["signed_pair_states_N"]
    assert m == result["same_seed_block_states_M"]
    b = [v*v for v in direct]
    offset_counts = {str(delta): sum(b[s]*b[s^delta] for s in range(32768))
                     for delta in result["offsets"]}
    assert {key: str(value) for key, value in offset_counts.items()} == result[
        "per_offset_two_block_states"]
    audit = {"status": "PASS_DIRECT_W15_OFFSET_COUNT_AUDIT",
             "source_sha256": freeze["source_sha256"],
             "protocol_sha256": sha(freeze_path),
             "binary_sha256": sha(binary),
             "direct_counts_sha256": sha(output),
             "all_32767_seed_counts_match": True,
             "selected_offsets_match": len(offset_counts),
             "signed_pair_states_N": n, "same_seed_block_states_M": m,
             "compile_wall_ns": build_ns,
             "enumeration_wall_ns": enumerate_ns,
             "total_wall_ns": time.monotonic_ns()-started}
    with (HERE / "direct_audit.json").open("x") as stream:
        json.dump(audit, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": audit["status"],
                      "enumeration_s": enumerate_ns/1e9}))


if __name__ == "__main__":
    main()
