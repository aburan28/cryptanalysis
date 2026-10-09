#!/usr/bin/env sage -python
"""Bounded exact 5+5 group join for the frozen N41 phi-chain public point."""

import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def leaf(onb, curve, basis, code, position):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("valid leaf lost its curve lift")
    return point


def decode(value):
    result = []
    for _ in range(5):
        result.append(value % 60)
        value //= 60
    return result


def build_options(onb, curve, codes, basis):
    options = []
    for position in range(12):
        rows = []
        for code in codes:
            point = leaf(onb, curve, basis, code, position)
            rows.append((code, 0, point))
            rows.append((code, 1, curve.neg(point)))
        if len(rows) != 60:
            raise ValueError("slot size changed")
        options.append(rows)
    return options


def point_sum(curve, points):
    result = None
    for point in points:
        result = curve.add(result, point)
    return result


def first_root_options(onb, curve, options, table):
    code0, code1 = table["first_link_leaf_codes"]
    phi = onb.fromCoords(table["selected_first_link_root"])
    root_x = onb.add(onb.inv(phi), onb.one())
    matches = {}
    for i, (_, _, p0) in enumerate(options[0]):
        if options[0][i][0] != code0:
            continue
        for j, (_, _, p1) in enumerate(options[1]):
            if options[1][j][0] != code1:
                continue
            total = curve.add(p0, p1)
            if total is not None and total[0] == root_x:
                matches[total] = (i, j)
    if len(matches) != 2:
        raise ValueError("selected first root has wrong signed branch count")
    return sorted(matches.items(), key=lambda row: row[0])


def pair_lists(curve, options):
    result = {}
    for first in (2, 4, 8, 10):
        result[first] = [curve.add(options[first][a][2],
                                   options[first + 1][b][2])
                         for a in range(60) for b in range(60)]
    return result


def five_sum(curve, options, pairs, ordinal, side):
    a, b, c, d, e = decode(ordinal)
    if side == "left":
        return curve.add(curve.add(pairs[2][a * 60 + b],
                                   pairs[4][c * 60 + d]),
                         options[6][e][2])
    return curve.add(curve.add(options[7][a][2],
                               pairs[8][b * 60 + c]),
                     pairs[10][d * 60 + e])


def candidate_ids(left, right, first_ids):
    a, b, c, d, e = decode(left)
    f, g, h, i, j = decode(right)
    return [*first_ids, a, b, c, d, e, f, g, h, i, j]


def verify_hit(curve, options, ids, endpoint, target):
    points = [options[position][index][2] for position, index in enumerate(ids)]
    if len({point[0] for point in points}) != 12:
        return False
    total = point_sum(curve, points)
    if total != endpoint or curve.mul(total, 4) != target:
        raise ValueError("hash hit failed exact group replay")
    return True


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    base_path, table_path = BASE / "protocol.json", BASE / "table.json"
    if (protocol["status"] != "FROZEN" or
            protocol["source_sha256"]["source_protocol"] != sha(base_path) or
            protocol["source_sha256"]["source_table"] != sha(table_path) or
            protocol["source_sha256"]["run_join"] != sha(Path(__file__)) or
            protocol["source_sha256"]["curves"] != sha(CODEGEN / "curves.py") or
            protocol["source_sha256"]["field"] != sha(CODEGEN / "field.py") or
            protocol["source_sha256"]["runtime"] != sha(HERE / "runtime_info.json") or
            json.loads((HERE / "runtime_info.json").read_text())["status"] != "verified"):
        raise ValueError("frozen source or Sage runtime changed")
    source, table = json.loads(base_path.read_text()), json.loads(table_path.read_text())
    if (source["field_degree"] != 41 or source["summands"] != 12 or
            source["subgroup_order"] != 549756390943 or
            source["valid_selector_count"] != 30 or
            protocol["target_count"] != 1 or protocol["batch"] is not False):
        raise ValueError("N41 public workload changed")
    onb = field.Onb(41)
    curve = curves.Curve(onb)
    basis, codes = table["basis_coordinate_masks"], table["valid_codes"]
    target = tuple(onb.fromCoords(value) for value in source["target_coordinates"])
    frozen_endpoint = tuple(onb.fromCoords(value)
                            for value in source["endpoint_coordinates"])

    setup_start = time.monotonic_ns()
    options = build_options(onb, curve, codes, basis)
    first = first_root_options(onb, curve, options, table)
    pairs = pair_lists(curve, options)
    left = {}
    rng = random.Random(protocol["left_sample_seed"])
    total_ordinal = 60 ** 5
    setup_cap = protocol["setup_wall_cap_seconds"] * 1_000_000_000
    online_cap = protocol["online_wall_cap_seconds"] * 1_000_000_000
    memory_cap = protocol["combined_rss_cap_bytes"]
    status = None
    left_draws = 0
    for index in range(protocol["left_samples"]):
        left_draws += 1
        ordinal = rng.randrange(total_ordinal)
        point = five_sum(curve, options, pairs, ordinal, "left")
        left.setdefault(point, ordinal)
        if index % 8192 == 0 and index:
            if peak_rss() > memory_cap:
                status = "SETUP_MEMORY_CAP"
                break
            if time.monotonic_ns() - setup_start > setup_cap:
                status = "SETUP_TIME_CAP"
                break
    setup_ns = time.monotonic_ns() - setup_start
    setup_peak = peak_rss()

    right_probes = 0
    hash_hits = 0
    distinct_x_rejections = 0
    witness = None
    online_ns = None
    check_ns = 0
    endpoint_conversion_ns = None
    if status is None:
        online_start = time.monotonic_ns()
        endpoint = curve.mul(target, pow(4, -1, source["subgroup_order"]))
        if endpoint != frozen_endpoint or curve.mul(endpoint, 4) != target:
            raise ValueError("public endpoint transport changed")
        endpoint_conversion_ns = time.monotonic_ns() - online_start
        offsets = [(curve.add(endpoint, curve.neg(root)), ids)
                   for root, ids in first]
        right_rng = random.Random(protocol["right_sample_seed"])
        for index in range(protocol["right_samples"]):
            ordinal = right_rng.randrange(total_ordinal)
            right_sum = five_sum(curve, options, pairs, ordinal, "right")
            negative_right = curve.neg(right_sum)
            right_probes += 1
            for residual, first_ids in offsets:
                needed = curve.add(residual, negative_right)
                left_ordinal = left.get(needed)
                if left_ordinal is None:
                    continue
                hash_hits += 1
                ids = candidate_ids(left_ordinal, ordinal, first_ids)
                check_start = time.monotonic_ns()
                if verify_hit(curve, options, ids, endpoint, target):
                    witness = {"slot_indices": ids,
                               "slot_code_sign": [[options[pos][slot][0],
                                                   options[pos][slot][1]]
                                                  for pos, slot in enumerate(ids)],
                               "raw_points": [[onb.toCoords(value) for value in
                                               options[pos][slot][2]]
                                              for pos, slot in enumerate(ids)],
                               "first_root_sign": list(first_ids),
                               "left_ordinal": left_ordinal,
                               "right_ordinal": ordinal}
                else:
                    distinct_x_rejections += 1
                check_ns += time.monotonic_ns() - check_start
                if witness is not None:
                    break
            if witness is not None:
                status = "VERIFIED_ORDINARY_RELATION"
                break
            if index % 8192 == 0 and index:
                if peak_rss() > memory_cap:
                    status = "ONLINE_MEMORY_CAP"
                    break
                if time.monotonic_ns() - online_start > online_cap:
                    status = "CENSORED_TIME"
                    break
        online_ns = time.monotonic_ns() - online_start
        if status is None:
            status = "FULL_SAMPLE_NO_RELATION"

    result = {"kind": "n41_phi_target_coupled_five_plus_five_pair_join",
              "status": status, "candidate_id": None, "run_id": None,
              "target_count": 1, "left_draws": left_draws,
              "left_distinct_group_points": len(left),
              "right_draws": right_probes, "hash_hits": hash_hits,
              "distinct_x_rejections": distinct_x_rejections,
              "setup_wall_ns": setup_ns, "setup_peak_rss_bytes": setup_peak,
              "target_dependent_online_wall_ns": online_ns,
              "target_endpoint_conversion_ns": endpoint_conversion_ns,
              "target_relation_check_ns": check_ns,
              "peak_rss_bytes": peak_rss(),
              "witness": witness,
              "source_sha256": {"protocol": sha(protocol_path),
                                "source_protocol": sha(base_path),
                                "source_table": sha(table_path),
                                "runtime": sha(HERE / "runtime_info.json"),
                                "run_join": sha(Path(__file__))}}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "left_draws", "left_distinct_group_points",
                       "right_draws", "hash_hits", "peak_rss_bytes")}))


if __name__ == "__main__":
    main()
