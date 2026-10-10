"""Freeze the N41 block-output census inputs, then run its two exact stages."""

import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INPUT = ROOT / "ecc2k130-ic-goal-20260929/n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, obj):
    with path.open("x") as target:
        json.dump(obj, target, sort_keys=True, indent=2)
        target.write("\n")


def main():
    binaries = {"census.cpp": digest(HERE / "census.cpp"),
                "census": digest(HERE / "census"),
                "rank.py": digest(HERE / "rank.py"),
                "run.py": digest(HERE / "run.py"),
                "helper.cpp": digest(HERE.parent / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp")}
    protocol = {
        "status": "FROZEN_BEFORE_CENSUS",
        "input_sha256": digest(INPUT),
        "source_sha256": binaries,
        "input": str(INPUT.relative_to(ROOT)),
        "curve": "GF(2)[t]/(t^41+t^3+1), y^2+xy=x^3+1",
        "point_law": "all distinct-column same-seed pair combinations in frozen rotation blocks 2 and 3; finite output x, distinct x per seed for rank",
        "feature_order": "constant; x bits 1..40; lexicographic quadratic products",
        "workers": 1,
        "census_timeout_seconds": 30,
        "rank_timeout_seconds": 120,
        "platform": platform.platform(),
    }
    write_new(HERE / "protocol.json", protocol)
    start = time.perf_counter_ns()
    result = subprocess.run([str(HERE / "census"), str(INPUT), str(HERE / "quad_outputs.tsv")],
                            capture_output=True, text=True, timeout=30)
    census_ns = time.perf_counter_ns() - start
    if result.returncode:
        raise RuntimeError(f"census failed: {result.stderr}")
    start = time.perf_counter_ns()
    result_rank = subprocess.run([sys.executable, str(HERE / "rank.py"),
                                  str(HERE / "quad_outputs.tsv"), str(HERE / "rank_result.json")],
                                 capture_output=True, text=True, timeout=120)
    rank_ns = time.perf_counter_ns() - start
    if result_rank.returncode:
        raise RuntimeError(f"rank failed: {result_rank.stderr}")
    write_new(HERE / "receipt.json", {
        "status": "CENSUS_AND_RANK_COMPLETE", "protocol_sha256": digest(HERE / "protocol.json"),
        "census_stdout": result.stdout, "rank_stdout": result_rank.stdout,
        "census_wall_ns": census_ns, "rank_wall_ns": rank_ns,
        "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "outputs_sha256": {"quad_outputs.tsv": digest(HERE / "quad_outputs.tsv"),
                           "rank_result.json": digest(HERE / "rank_result.json")},
    })
    print(result.stdout.strip(), result_rank.stdout.strip())


if __name__ == "__main__":
    main()
