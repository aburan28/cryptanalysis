#!/usr/bin/env python3
"""Independent streaming Python GF(2) elimination for every exact seed bin."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def features(x: int) -> int:
    if x & 1 or x >> 41:
        raise ValueError("invalid N41 x coordinate encoding")
    active = [i for i in range(40) if (x >> (i + 1)) & 1]
    value = 1
    for i in active:
        value |= 1 << (i + 1)
    for a, i in enumerate(active):
        for j in active[a + 1:]:
            index = 41 + i * (79 - i) // 2 + j - i - 1
            value |= 1 << index
    return value


def peak_rss_bytes():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def main() -> None:
    output = HERE / "saturation_audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent saturation audit")
    frozen = json.loads((HERE / "saturation_audit_protocol.json").read_text())
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"audit input changed: {name}")
    if sha(Path(__file__)) != frozen["audit_source_sha256"]:
        raise ValueError("audit source changed")
    start = time.monotonic_ns()
    bases = [[0] * 821 for _ in range(3969)]
    ranks = [0] * 3969
    counts = [0] * 3969
    rows = 0
    status = "RUNNING"
    with (HERE / "x_orbits.bin").open("rb") as stream:
        while True:
            raw = stream.read(12)
            if not raw:
                break
            if len(raw) != 12:
                raise ValueError("truncated exact x orbit")
            s, t = raw[0], raw[1]
            if not (1 <= s <= 63 and 1 <= t <= 63):
                raise ValueError("invalid seed bin")
            bin_index = (s - 1) * 63 + t - 1
            counts[bin_index] += 1
            x = int.from_bytes(raw[2:8], "little")
            row = features(x)
            basis = bases[bin_index]
            while row:
                pivot = row.bit_length() - 1
                if basis[pivot]:
                    row ^= basis[pivot]
                else:
                    basis[pivot] = row
                    ranks[bin_index] += 1
                    break
            rows += 1
            if rows % 4096 == 0:
                if time.monotonic_ns() - start >= frozen["wall_cap_seconds"] * 10**9:
                    status = "TIME_CAP"
                    break
                if peak_rss_bytes() >= frozen["rss_cap_bytes"]:
                    status = "MEMORY_CAP"
                    break
    if status == "RUNNING":
        result = json.loads((HERE / "saturation_result.json").read_text())
        if rows != 1583568 or sum(counts) != rows:
            status = "ROW_COUNT_MISMATCH"
        elif any(rank != min(size, 821) for size, rank in zip(counts, ranks)):
            status = "RANK_SATURATION_MISMATCH"
        elif sum(821 - rank for rank in ranks) != result["total_quadratic_kernel_dimension"]:
            status = "KERNEL_DIMENSION_MISMATCH"
        else:
            status = "PASS_INDEPENDENT_ALL_BIN_GF2_RANK"
    audit = {
        "status": status,
        "kind": "n41_all_bin_quadratic_rank_independent_python_elimination",
        "curve_id": frozen["curve_id"],
        "processed_x_orbits": rows,
        "checked_bins": 3969 if rows == 1583568 else None,
        "bins_with_rank_below_min_size_and_821":
            sum(rank < min(size, 821) for size, rank in zip(counts, ranks))
            if rows == 1583568 else None,
        "total_kernel_dimension": sum(821 - rank for rank in ranks)
            if rows == 1583568 else None,
        "wall_ns": time.monotonic_ns() - start,
        "peak_rss_bytes": peak_rss_bytes(),
        "audit_protocol_sha256": sha(HERE / "saturation_audit_protocol.json"),
        "audit_source_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
