#!/usr/bin/env sage -python
"""Independent Sage coordinate and M4RI monomial-rank audit."""

import hashlib
import json
import random
import shutil
import struct
import subprocess
from pathlib import Path

from sage.all import GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DOMAIN = GOAL / "n41_w8_two_pair_backward_20261009"
PREFIX = Path("/var/tmp/sage-10.9-current/local")
N = 41
DIM = 11522


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def indices(path):
    data = Path(path).read_bytes()
    if len(data) != 4*DIM:
        raise ValueError("witness row-index payload changed")
    return list(struct.unpack("<"+"I"*DIM, data))


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if protocol["source_sha256"] != {
            path: sha(path) for path in protocol["source_sha256"]}:
        raise ValueError("source identity changed")
    if (result["status"] != "FULL_CUBIC_RANK" or
            result["source_sha256"] != protocol["source_sha256"] or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            result["table_sha256"] != sha(DOMAIN / "table.bin") or
            result["phi_sha256"] != sha(HERE / "phi.bin") or
            result["x_witness_sha256"] != sha(HERE / "x_witness.bin") or
            result["phi_witness_sha256"] != sha(HERE / "phi_witness.bin") or
            result["monomial_dimension"] != DIM or
            result["total_stage_ns"] > protocol["cap_ns"] or
            result["peak_rss_bytes"] > protocol["rss_cap_bytes"]):
        raise ValueError("frozen rank result failed receipt checks")
    phase_sum = sum(result[key] for key in
                    ("phi_construction_ns", "x_rank_ns", "phi_rank_ns",
                     "witness_serialization_ns"))
    if phase_sum != result["total_stage_ns"]:
        raise ValueError("rank phase times do not sum to charged stage")
    table = (DOMAIN / "table.bin").read_bytes()
    phi = (HERE / "phi.bin").read_bytes()
    count = len(table)//15
    if len(table) != count*15 or len(phi) != count*6:
        raise ValueError("coordinate files have invalid record lengths")
    chosen = {}
    for label in ("x", "phi"):
        row_indices = indices(HERE / f"{label}_witness.bin")
        processed = result[f"{label}_rows_processed"]
        allowed = {(k*protocol["row_stride"]+protocol["row_offset"]) % count
                   for k in range(processed)}
        if (len(set(row_indices)) != DIM or
                not set(row_indices).issubset(allowed) or
                result[f"{label}_rank"] != DIM):
            raise ValueError("saved independent-row index set changed")
        chosen[label] = row_indices
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, name="t", modulus=t**41+t**3+1)
    def elem(value):
        return field(ring([(int(value) >> bit) & 1 for bit in range(N)]))
    def integer(value):
        return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))
    rng = random.Random(20261009182400)
    coordinate_checks = set(chosen["phi"]) | set(rng.sample(range(count), 100))
    for index in coordinate_checks:
        x = int.from_bytes(table[index*15:index*15+6], "little")
        observed = int.from_bytes(phi[index*6:index*6+6], "little")
        if x == 1 or observed != integer(1/(elem(x)+1)):
            raise ValueError(f"independent Sage phi mismatch at {index}")
    library = PREFIX / "lib/libm4ri.dylib"
    if not library.is_file():
        raise FileNotFoundError("checked Sage M4RI library unavailable")
    compiler = shutil.which("g++")
    if not compiler:
        raise FileNotFoundError("g++ unavailable")
    binary = HERE / "native_audit"
    command = [compiler, "-O3", "-std=c++17", "-I"+str(PREFIX / "include"),
               str(HERE / "native_audit.cpp"), "-L"+str(PREFIX / "lib"),
               "-lm4ri", "-Wl,-rpath,"+str(PREFIX / "lib")]
    if __import__("sys").platform == "darwin":
        command.append("-Wl,-no_uuid")
    command += ["-o", str(binary)]
    build = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if build.returncode:
        raise RuntimeError(f"native audit compile failed: {build.stderr[-1200:]}")
    args = [str(binary), str(DOMAIN / "table.bin"), str(HERE / "phi.bin"),
            str(HERE / "x_witness.bin"), str(HERE / "phi_witness.bin")]
    process = subprocess.run(args, capture_output=True, text=True, timeout=240)
    if process.returncode:
        raise RuntimeError(f"native independent rank failed: {process.stderr[-1200:]}")
    native = json.loads(process.stdout)
    if (native != {"x_rank": DIM, "phi_rank": DIM, "witness_rows": DIM}):
        raise ValueError("independent M4RI rank is incomplete")
    audited = {"status": "PASS_INDEPENDENT_CUBIC_RANK_AUDIT",
               "proposal_id": result["proposal_id"], "candidate_id": None,
               "curve_id": result["curve_id"],
               "protocol_sha256": sha(HERE / "protocol.json"),
               "table_sha256": sha(DOMAIN / "table.bin"),
               "phi_sha256": sha(HERE / "phi.bin"),
               "sage_phi_coordinate_checks": len(coordinate_checks),
               "native_rank": native,
               "native_binary_sha256": sha(binary),
               "m4ri_library_sha256": sha(library),
               "compiler_command": command}
    output.write_text(json.dumps(audited, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"status": audited["status"],
                      "sage_phi_coordinate_checks": len(coordinate_checks),
                      "native_rank": native}, sort_keys=True))


if __name__ == "__main__":
    main()
