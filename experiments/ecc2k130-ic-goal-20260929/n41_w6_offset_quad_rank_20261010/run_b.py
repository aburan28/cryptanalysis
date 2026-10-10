"""Freeze and run the rotated second same-seed block census and rank."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE.parent / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, record):
    with path.open("x") as output:
        json.dump(record, output, sort_keys=True, indent=2)
        output.write("\n")


def main():
    sources = {name: digest(HERE / name) for name in
               ("census_b.cpp", "census_b", "rank.py", "run_b.py")}
    sources["input"] = digest(INPUT)
    write_new(HERE / "protocol_b.json", {
        "status": "FROZEN_BEFORE_SECOND_BLOCK_CENSUS",
        "source_sha256": sources,
        "block_windows": [4, 5],
        "feature_order": "constant; x bits 1..40; lexicographic quadratic products",
        "workers": 1, "census_timeout_seconds": 30,
        "rank_timeout_seconds": 120,
    })
    begin = time.perf_counter_ns()
    census = subprocess.run([str(HERE / "census_b"), str(INPUT),
                             str(HERE / "quad_outputs_b.tsv")],
                            capture_output=True, text=True, timeout=30, check=True)
    census_ns = time.perf_counter_ns() - begin
    begin = time.perf_counter_ns()
    rank = subprocess.run([sys.executable, str(HERE / "rank.py"),
                           str(HERE / "quad_outputs_b.tsv"), str(HERE / "rank_b.json")],
                          capture_output=True, text=True, timeout=120, check=True)
    rank_ns = time.perf_counter_ns() - begin
    write_new(HERE / "receipt_b.json", {
        "status": "SECOND_BLOCK_CENSUS_AND_RANK_COMPLETE",
        "protocol_sha256": digest(HERE / "protocol_b.json"),
        "census_stdout": census.stdout, "rank_stdout": rank.stdout,
        "census_wall_ns": census_ns, "rank_wall_ns": rank_ns,
        "outputs_sha256": {name: digest(HERE / name)
                           for name in ("quad_outputs_b.tsv", "rank_b.json")},
    })
    print(census.stdout.strip(), rank.stdout.strip())


if __name__ == "__main__":
    main()
