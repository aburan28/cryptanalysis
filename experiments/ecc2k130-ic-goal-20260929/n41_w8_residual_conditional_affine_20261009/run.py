#!/usr/bin/env python3
"""Frozen full-domain conditional-affine feature rank on N41 W8 residuals."""

import hashlib
import json
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DOMAIN = GOAL / "n41_w8_two_pair_backward_20261009"
COORD = GOAL / "n41_two_pair_residual_degree3_20261009"
GEOMETRY = GOAL / "n41_w8_fixed_sum_backward_20261009/geometry.json"
PROPOSAL_ID = "Q20261009185000"
CAP_NS = 300_000_000_000
RSS_CAP = 4 * 1024**3


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(mask):
    if mask & 32 or mask >= 256:
        raise ValueError("unexpected canonical mask")
    return (mask & 31) | ((mask >> 6) << 5)


def labels_for(record, states4, states5):
    branch, i, j = record[12:15]
    if branch >= 4 or i >= len(states4) or j >= len(states5):
        raise ValueError("invalid record label")
    a = states4[i]
    b = states5[j]
    if len(set(a["columns"] + b["columns"])) != 4:
        raise ValueError("record has repeated factor-base column")
    return (branch | (compact(a["a"]) << 2) | (compact(b["a"]) << 9) |
            (a["sign_a"] << 16) | (a["sign_b"] << 17) |
            (b["sign_a"] << 18) | (b["sign_b"] << 19))


def source_paths():
    return [HERE / "run.py", HERE / "native_rank.cpp", HERE / "audit.py",
            HERE / "independent_rank.py",
            HERE / "sage_runtime_info.json",
            DOMAIN / "table.bin", DOMAIN / "audit.json", COORD / "phi.bin",
            COORD / "audit.json", GEOMETRY]


def main():
    if (HERE / "result.json").exists():
        raise FileExistsError("preserve first frozen result")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if (protocol["source_sha256"] != {str(p): sha(p) for p in source_paths()} or
            protocol["cap_ns"] != CAP_NS or protocol["rss_cap_bytes"] != RSS_CAP):
        raise ValueError("frozen source, input, or cap changed")
    table = (DOMAIN / "table.bin").read_bytes()
    geometry = json.loads(GEOMETRY.read_text())
    states4 = geometry["blocks"][4]["states"]
    states5 = geometry["blocks"][5]["states"]
    if len(table) != 99456 * 15:
        raise ValueError("frozen table size changed")
    setup_start = time.monotonic_ns()
    compiler = shutil.which("g++")
    if not compiler:
        raise FileNotFoundError("g++ unavailable")
    prefix = Path("/var/tmp/sage-10.9-current/local")
    library = prefix / "lib/libm4ri.dylib"
    if not library.is_file():
        raise FileNotFoundError("accepted M4RI library unavailable")
    command = [compiler, "-O3", "-std=c++17", "-I" + str(prefix / "include"),
               str(HERE / "native_rank.cpp"), "-L" + str(prefix / "lib"),
               "-lm4ri", "-Wl,-rpath," + str(prefix / "lib")]
    if sys.platform == "darwin":
        command.append("-Wl,-no_uuid")
    binary = HERE / "native_rank"
    command += ["-o", str(binary)]
    build = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if build.returncode:
        raise RuntimeError(build.stderr[-1200:])
    setup_ns = time.monotonic_ns() - setup_start
    start = time.monotonic_ns()
    payload = bytearray()
    for index in range(0, len(table), 15):
        payload.extend(labels_for(table[index:index+15], states4, states5).to_bytes(4, "little"))
    labels_path = HERE / "labels.bin"
    labels_path.write_bytes(payload)
    label_ns = time.monotonic_ns() - start
    process = subprocess.run([str(binary), str(DOMAIN / "table.bin"),
                              str(COORD / "phi.bin"), str(labels_path)],
                             capture_output=True, text=True, timeout=240)
    rank_ns = time.monotonic_ns() - start - label_ns
    result = {"status": "FULL_DOMAIN_RANK" if process.returncode == 0 else "NATIVE_FAILURE",
              "proposal_id": PROPOSAL_ID, "candidate_id": None, "run_id": None,
              "curve_id": geometry["curve_id"], "table_rows": len(table)//15,
              "label_build_ns": label_ns, "native_rank_ns": rank_ns,
              "charged_structural_ns": time.monotonic_ns() - start,
              "setup_compile_ns": setup_ns,
              "peak_rss_bytes": (max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                      resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss) *
                                 (1 if sys.platform == "darwin" else 1024)),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": protocol["source_sha256"],
              "labels_sha256": sha(labels_path), "native_binary_sha256": sha(binary),
              "m4ri_library_sha256": sha(library), "compiler_command": command,
              "native_stdout": process.stdout, "native_stderr": process.stderr,
              "native_returncode": process.returncode}
    if process.returncode == 0:
        result["rank"] = json.loads(process.stdout)
    if result["charged_structural_ns"] > CAP_NS:
        result["status"] = "TIME_CAP_EXCEEDED"
    if result["peak_rss_bytes"] > RSS_CAP:
        result["status"] = "MEMORY_CAP_EXCEEDED"
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "rank", "charged_structural_ns", "peak_rss_bytes") if k in result}, sort_keys=True))


if __name__ == "__main__":
    main()
