#!/usr/bin/env python3
"""Independently replay frozen pair sums with the checked Sage curve."""

from __future__ import annotations

import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = HERE / "sage_audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent arithmetic audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    production = json.loads((HERE / "production.json").read_text())
    control = json.loads((HERE / "rank_control.json").read_text())
    runtime = json.loads((HERE / "sage_runtime_info.json").read_text())
    if runtime["status"] != "verified" or control["status"] != "EXIT_SUCCESS":
        raise ValueError("checked Sage runtime or rank execution missing")
    row_file = HERE / "rows.bin"
    if (digest(row_file) != production["rows_sha256"] or
            control["rows_sha256"] != production["rows_sha256"]):
        raise ValueError("frozen rank rows changed")
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    if geometry["curve_id"] != protocol["curve_id"]:
        raise ValueError("curve ID changed")
    start = time.monotonic_ns()
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**41, "t", modulus=t**41 + t**3 + 1)
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)

    def decode(value: int):
        return field(ring([(value >> bit) & 1 for bit in range(41)]))

    def point(raw):
        return curve(decode(raw[0]), decode(raw[1]))

    def encode(p):
        return [sum(int(bit) << i for i, bit in enumerate(p[0].polynomial().list())),
                sum(int(bit) << i for i, bit in enumerate(p[1].polynomial().list()))]

    rotations = protocol["pair_rotations"]
    source_rows = [geometry["point_rows_by_unique_rotation"][str(r)] for r in rotations]
    source_points = [[point(row) for row in rows] for rows in source_rows]
    subgroup_order = protocol["subgroup_order"]
    if any(subgroup_order * p != zero for points in source_points for p in points):
        raise ValueError("factor-base point outside subgroup")
    target = point(protocol["public_target_q"])
    if subgroup_order * target != zero:
        raise ValueError("public target outside subgroup")
    domains = []
    for rows, points in zip(source_rows, source_points):
        states = []
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[i][2] == rows[j][2]:
                    continue
                states.append((rows[i][3] ^ rows[j][3], points[i] + points[j],
                               (1 << rows[i][2]) | (1 << rows[j][2])))
        if len(states) != 1956:
            raise ValueError("Sage pair domain changed")
        domains.append(states)
    raw = row_file.read_bytes()
    if len(raw) != protocol["row_count"] * 18:
        raise ValueError("row count changed")
    rng = random.Random(protocol["audit_seed"])
    sample = sorted(set(range(16)) | set(rng.sample(range(protocol["row_count"]),
                                                  protocol["audit_rows"])))
    for index in sample:
        row = raw[index * 18:(index + 1) * 18]
        seed_left, seed_right = row[0], row[1]
        x = int.from_bytes(row[2:8], "little")
        y = int.from_bytes(row[8:14], "little")
        i = int.from_bytes(row[14:16], "little")
        j = int.from_bytes(row[16:18], "little")
        left, right = domains[0][i], domains[1][j]
        if left[2] & right[2]:
            raise ValueError(f"repeated folded column in row {index}")
        summed = left[1] + right[1]
        if (summed == zero or [seed_left, seed_right] != [left[0], right[0]] or
                encode(summed) != [x, y]):
            raise ValueError(f"independent group replay differs in row {index}")
    active_seed = 0
    active_coordinate = 0
    for offset in range(0, len(raw), 18):
        row = raw[offset:offset + 18]
        active_seed += row[0].bit_count() + row[1].bit_count()
        active_coordinate += (int.from_bytes(row[2:8], "little") >> 1).bit_count()
        active_coordinate += int.from_bytes(row[8:14], "little").bit_count()
    rank = json.loads((HERE / "rank.json").read_text())
    if (active_seed != rank["active_seed_sum"] or
            active_coordinate != rank["active_coordinate_sum"]):
        raise ValueError("independent input-bit population differs")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    audit = {"status": "PASS_INDEPENDENT_SAGE_GROUP_REPLAY",
             "curve_id": protocol["curve_id"], "proposal_id": protocol["proposal_id"],
             "source_subgroup_points_checked": sum(map(len, source_points)),
             "public_target_subgroup_checked": True,
             "pair_domain_sizes": list(map(len, domains)),
             "exact_group_sums_replayed": len(sample),
             "sample_indices_sha256": hashlib.sha256(
                 ",".join(map(str, sample)).encode()).hexdigest(),
             "active_seed_sum": active_seed,
             "active_coordinate_sum": active_coordinate,
             "runtime_sha256": digest(HERE / "sage_runtime_info.json"),
             "rows_sha256": digest(row_file),
             "rank_sha256": digest(HERE / "rank.json"),
             "audit_source_sha256": digest(Path(__file__)),
             "audit_wall_ns": time.monotonic_ns() - start,
             "peak_rss_bytes": peak}
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": audit["status"], "replayed": len(sample),
                      "wall_s": audit["audit_wall_ns"] / 1e9}))


if __name__ == "__main__":
    main()
