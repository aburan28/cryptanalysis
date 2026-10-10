#!/usr/bin/env python3
"""Independent packed-file and group replay for the 64-seed N131 panel."""

import collections
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MIXED = ROOT / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
OLD = ROOT / "n131_w14_coupled_fouratom_inverse_20261010/inputs.json"
SUPPORT = ROOT / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
COUNT = ROOT / "n131_w14_fixed_seed_support_gate_20261010/result_bounds.json"
ARITH = ROOT / "n41_two_free_pair_occupancy_20261009/arithmetic_snapshot.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


import importlib.util
spec = importlib.util.spec_from_file_location("stream_independent_arithmetic", ARITH)
arith = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arith)
f = arith.Field(131, [0, 1, 2, 13])
curve = arith.Curve(f, 0)


def frob(value, count):
    for _ in range(count):
        value = f.mul(value, value)
    return value


def rotate(point, count):
    return frob(point[0], count), frob(point[1], count)


prepare = json.loads((HERE / "prepare_protocol.json").read_text())
old_query = json.loads((HERE / "query_protocol.json").read_text())
query = json.loads((HERE / "query_protocol_v2.json").read_text())
setup = json.loads((HERE / "setup.json").read_text())
parent = json.loads((HERE / "query_parent_v2.json").read_text())
failure = json.loads((HERE / "query_failure_v1.json").read_text())
assert sha(HERE / "stream_v1.cpp") == prepare["source_sha256"]["stream.cpp"]
assert sha(HERE / "stream_v1") == prepare["source_sha256"]["stream"]
assert sha(HERE / "index.bin") == old_query["source_sha256"]["index.bin"]
assert sha(HERE / "index.bin") == query["source_sha256"]["index.bin"]
assert parent["protocol_sha256"] == sha(HERE / "query_protocol_v2.json")
assert failure["status"] == "PRODUCER_FAILURE_BAD_INDEX_MAGIC"
assert setup["status"] == "COMPLETE_PACKED_SEED_PREPARE"

columns = {}
for line in SUPPORT.read_text().splitlines():
    mask, column = map(int, line.split())
    assert mask not in columns
    columns[mask] = column
assert len(columns) == 8220

data = (HERE / "index.bin").read_bytes()
assert data[:8] == b"S3STRM1\x00"
lo, hi = struct.unpack_from("<HH", data, 8)
assert (lo, hi) == (1, 64)
offset = 12
pair_total = entry_total = equation_checks = 0
for seed in range(lo, hi + 1):
    actual, nl, nr = struct.unpack_from("<HHH", data, offset)
    offset += 6
    assert actual == seed and nl == nr
    expected_pairs = sum(1 for a in columns if a < (a ^ seed)
                         and (a ^ seed) in columns
                         and columns[a] != columns[a ^ seed])
    assert nl == 2 * expected_pairs
    pair_total += expected_pairs
    entry_total += nl
    seen = []
    for side, count, width in ((0, nl, 38), (1, nr, 21)):
        descriptor_count = collections.Counter()
        samples = {0, count // 2, count - 1}
        for index in range(count):
            record = data[offset:offset + width]
            assert len(record) == width
            offset += width
            coordinate = int.from_bytes(record[:17], "little")
            assert 0 < coordinate < 2**131
            if side == 0:
                packed_h = int.from_bytes(record[17:34], "little")
                h, trace = packed_h & (2**131 - 1), packed_h >> 131
                assert trace in (0, 1)
                descriptor = struct.unpack_from("<I", record, 34)[0]
            else:
                descriptor = struct.unpack_from("<I", record, 17)[0]
            a, b = descriptor & 16383, descriptor >> 14
            assert a < b and a ^ b == seed
            assert a in columns and b in columns and columns[a] != columns[b]
            descriptor_count[descriptor] += 1
            if index not in samples:
                continue
            p = f.mul(a << 1, b << 1)
            expected_product = 0
            for bit in range(14):
                if a >> bit & 1:
                    expected_product ^= b << (bit + 2)
            assert p == expected_product
            pr = frob(p, 26 if side == 0 else 39)
            sr = frob(seed << 1, 26 if side == 0 else 39)
            residual = (f.mul(1 ^ f.mul(pr, pr), f.mul(coordinate, coordinate))
                        ^ f.mul(pr, coordinate) ^ f.mul(sr, sr))
            assert residual == 0
            if side == 0:
                ac = f.mul(coordinate ^ f.inv(coordinate),
                           coordinate ^ f.inv(coordinate))
                assert f.mul(h, h) ^ h ^ ac == trace
            equation_checks += 1
        assert len(descriptor_count) == expected_pairs
        assert set(descriptor_count.values()) == {2}
        seen.append(descriptor_count)
    assert seen[0] == seen[1]
assert offset == len(data) == setup["packed_bytes"]
assert pair_total == setup["usable_mask_pairs"] == 132101
assert entry_total == setup["entries_per_rotation"] == 264202

positive = json.loads((HERE / "positive_v2.json").read_text())
control = json.loads((HERE / "trace_zero_control_v2.json").read_text())
for case, row in (("positive", positive), ("trace_zero_control", control)):
    assert row["status"] == "COMPLETE_PACKED_SEED_QUERY"
    assert row["seeds_queried"] == 64
    assert row["left_entries_checked"] == entry_total
    assert row["peak_rss_bytes"] < query["rss_cap_bytes"]
    assert row["query_ns"] < query["query_cap_seconds_per_case"] * 10**9
    assert sha(HERE / f"{case}_v2.json") == next(
        p["result_sha256"] for p in parent["rows"] if p["case"] == case)
assert len(positive["hits"]) == 1 and control["hits"] == []
hit = positive["hits"][0]
assert hit["seed"] == 1 and hit["masks"] == [18, 19, 24, 25]
assert hit["p"] == [1112, 0, 0] and hit["q"] == [1376, 0, 0]

panel = json.loads(OLD.read_text())["panels"]["131"]
mixed = json.loads(MIXED.read_text())["panels"]["131"]
assert panel["masks"] == hit["masks"] == mixed["source_masks"]
points = [tuple(p) for p in panel["raw_diagonal_atoms"]]
assert all(curve.on_curve(point) for point in points)
rotated = [rotate(point, 26 if index < 2 else 39)
           for index, point in enumerate(points)]
total = None
for point in rotated:
    total = curve.add(total, point)
assert total == tuple(mixed["raw_sum"])
assert f.inv(total[0]) == mixed["positive_z"]
projected = curve.mul(4, total)
assert projected == tuple(mixed["projected_sum"])
assert curve.mul(int(panel["subgroup_order"]), projected) is None

full = json.loads(COUNT.read_text())["n131"]
assert full["usable_unordered_mask_pairs"] == 33780028
all_entries_upper = 2 * full["usable_unordered_mask_pairs"]
all_packed_bytes_upper = 12 + full["seed_count"] * 6 + 59 * all_entries_upper
projection_s = positive["query_ns"] / 1e9 * all_entries_upper / entry_total
receipt = {"status": "PASS_INDEPENDENT_PACKED_STREAM_AUDIT",
           "source_sha256": {"audit.py": sha(Path(__file__)),
                             "arithmetic_snapshot.py": sha(ARITH),
                             "index.bin": sha(HERE / "index.bin"),
                             "setup.json": sha(HERE / "setup.json"),
                             "query_protocol_v2.json": sha(HERE / "query_protocol_v2.json"),
                             "positive_v2.json": sha(HERE / "positive_v2.json"),
                             "trace_zero_control_v2.json": sha(HERE / "trace_zero_control_v2.json"),
                             "source_points.json": sha(OLD),
                             "mixed_inputs.json": sha(MIXED),
                             "full_pair_count.json": sha(COUNT)},
           "seed_count": 64, "usable_mask_pairs": pair_total,
           "entries_per_rotation": entry_total,
           "sampled_pair_equations": equation_checks,
           "positive_group_replay": True,
           "control_hits": 0,
           "projection": {"status": "UNMEASURED_FULL_SEED_PROJECTION",
                          "full_seed_count": full["seed_count"],
                          "full_entries_per_rotation_upper": all_entries_upper,
                          "full_packed_bytes_upper": all_packed_bytes_upper,
                          "scaled_positive_query_seconds": projection_s}}
(HERE / "terminal_audit.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": receipt["status"],
                  "equation_checks": equation_checks,
                  "projection_seconds": projection_s}, sort_keys=True))
