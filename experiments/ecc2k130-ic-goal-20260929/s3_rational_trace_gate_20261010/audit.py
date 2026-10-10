#!/usr/bin/env python3
"""Check trace rationality and local S3 solvability on archived support."""

import hashlib
import importlib.util
import json
import resource
import struct
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARITH = ROOT / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py"
SCREEN = ROOT / "n41_n131_diagonal_atom_20261010/screen.json"
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
INDEX = ROOT / "n131_mixed_s3_stream64_20261010/index.bin"
SETUP = ROOT / "n131_mixed_s3_stream64_20261010/setup.json"
sources = {"audit.py": Path(__file__), "arithmetic_snapshot.py": ARITH,
           "n41_screen.json": SCREEN, "mixed_inputs.json": MIXED,
           "n131_index.bin": INDEX, "n131_index_setup.json": SETUP}
protocol = json.loads((HERE / "protocol.json").read_text())
assert protocol["source_sha256"] == {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in sources.items()}

spec = importlib.util.spec_from_file_location("independent_trace_arithmetic", ARITH)
arith = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arith)
started = time.monotonic_ns()


def trace_mask(field, degree):
    mask = 0
    for basis in range(degree):
        value = 1 << basis
        total = 0
        for _ in range(degree):
            total ^= value
            value = field.mul(value, value)
        assert total in (0, 1)
        mask |= total << basis
    return mask


def frob(field, value, steps):
    for _ in range(steps):
        value = field.mul(value, value)
    return value


def rotate(field, point, steps):
    return (frob(field, point[0], steps), frob(field, point[1], steps))


def s3(field, a, b, z):
    product = field.mul(field.mul(a, b), z)
    total = a ^ b ^ z
    return field.mul(total, total) ^ product ^ field.mul(product, product)


mixed = json.loads(MIXED.read_text())["panels"]
f41 = arith.Field(41, [0, 3])
e41 = arith.Curve(f41, 0)
mask41 = trace_mask(f41, 41)
screen = json.loads(SCREEN.read_text())
columns = {row["mask"]: row["source_column"] for row in screen["slots"][0]}
points = {}
for row in screen["raw_audit"]:
    p = tuple(row["raw_pair_point"])
    assert e41.on_curve(p)
    points[row["mask"]] = (p, e41.neg(p))
assert len(points) == 32 and len(set(columns.values())) == 26

pair_states = 0
coordinates = [dict(), dict()]
masks = sorted(points)
for i, a in enumerate(masks):
    for b in masks[i + 1:]:
        if columns[a] == columns[b]:
            continue
        for pa in points[a]:
            for pb in points[b]:
                pair = e41.add(pa, pb)
                if pair is None or pair[0] == 0:
                    continue
                pair_states += 1
                for side, rotation in enumerate((10, 15)):
                    rotated = rotate(f41, pair, rotation)
                    c = f41.inv(rotated[0])
                    coordinates[side].setdefault(c, rotated)
assert pair_states == 1956
assert [len(v) for v in coordinates] == [978, 978]


def trace_reciprocal(field, mask, c):
    return ((c ^ field.inv(c)) & mask).bit_count() & 1


assert all(trace_reciprocal(f41, mask41, c) == 0
           for side in coordinates for c in side)
n41 = {}
for case in ("positive", "trace_zero_control"):
    z = mixed["41"]["positive_z" if case == "positive"
                    else "trace_zero_control_z"]
    assert trace_reciprocal(f41, mask41, z) == 0
    target_points = arith.points_with_x(e41, f41.inv(z))
    assert len(target_points) == 2
    target = target_points[0]
    good = one_branch = two_branches = 0
    for c, point in coordinates[0].items():
        roots = set()
        for candidate in (target, e41.neg(target)):
            total = e41.add(point, candidate)
            if total is None or total[0] == 0:
                continue
            d = f41.inv(total[0])
            assert s3(f41, c, d, z) == 0
            roots.add(d)
        assert roots
        good += 1
        if len(roots) == 1:
            one_branch += 1
        else:
            assert len(roots) == 2
            two_branches += 1
    n41[case] = {"proposed_z": z, "rational_left_coordinates": good,
                 "one_distinct_s3_root": one_branch,
                 "two_distinct_s3_roots": two_branches,
                 "target_trace_bit": 0}

f131 = arith.Field(131, [0, 1, 2, 13])
mask131 = trace_mask(f131, 131)
data = INDEX.read_bytes()
assert data[:8] == b"S3STRM1\x00"
first, last = struct.unpack_from("<HH", data, 8)
assert (first, last) == (1, 64)
offset = 12
flag_counts = [0, 0]
sampled = 0
for seed in range(first, last + 1):
    actual, left_count, right_count = struct.unpack_from("<HHH", data, offset)
    offset += 6
    assert actual == seed and left_count == right_count
    for index in range(left_count):
        c = int.from_bytes(data[offset:offset + 17], "little")
        hword = int.from_bytes(data[offset + 17:offset + 34], "little")
        flag = hword >> 131
        assert flag in (0, 1)
        flag_counts[flag] += 1
        if index in (0, left_count // 2, left_count - 1):
            assert trace_reciprocal(f131, mask131, c) == flag
            sampled += 1
        offset += 38
    offset += right_count * 21
assert offset == len(data)
assert flag_counts == [264202, 0]
assert sampled == 192
assert json.loads(SETUP.read_text())["entries_per_rotation"] == sum(flag_counts)
n131 = {}
for case in ("positive", "trace_zero_control"):
    z = mixed["131"]["positive_z" if case == "positive"
                     else "trace_zero_control_z"]
    n131[case] = {"proposed_z": z,
                  "target_trace_bit": trace_reciprocal(f131, mask131, z)}
assert all(row["target_trace_bit"] == 0 for row in n131.values())

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
assert 0 < rss < protocol["rss_cap_bytes"]
elapsed = time.monotonic_ns() - started
assert elapsed < protocol["cap_seconds"] * 10**9
result = {"status": "PASS_S3_RATIONAL_TRACE_SUPPORT_GATE",
          "protocol_sha256": hashlib.sha256((HERE / "protocol.json").read_bytes()).hexdigest(),
          "n41": {"signed_pair_states": pair_states,
                  "distinct_outputs_per_rotation": [len(v) for v in coordinates],
                  "cases": n41},
          "n131": {"seed_count": 64, "left_entries": sum(flag_counts),
                   "left_trace_bit_counts": flag_counts,
                   "independent_trace_samples": sampled,
                   "cases": n131},
          "wall_ns": elapsed, "peak_process_rss_bytes": rss}
(HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": result["status"],
                  "n41_roots": {k: v["two_distinct_s3_roots"]
                                for k, v in n41.items()},
                  "n131_trace_bits": flag_counts}, sort_keys=True))
