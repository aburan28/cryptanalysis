#!/usr/bin/env sage -python
"""Exact cached known-sum inverse for same-rotation N131 d13 leaf pairs."""

import hashlib
import json
import random
import resource
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
PIPELINE = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_full_pipeline"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
sys.path.insert(0, str(CODEGEN))
import curves
import field

N = 131
DIM = 13
DOMAIN = 1 << DIM
MAGIC = b"D13PIV1\0"
HEADER = struct.Struct("<8sHBB")
RECORD_BYTES = 20


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def phi_from_code(onb, basis, code):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    return onb.fromCoords(mask)


def aval(onb, value):
    return onb.add(onb.sqr(value), value)


def echelon(columns):
    pivots = {}
    kernel = []
    for bit, column in enumerate(columns):
        word = column
        coefficient = 1 << bit
        while word:
            leading = word.bit_length() - 1
            if leading not in pivots:
                pivots[leading] = (word, coefficient)
                break
            pivot, combo = pivots[leading]
            word ^= pivot
            coefficient ^= combo
        else:
            kernel.append(coefficient)
    return pivots, kernel


def solve(pivots, word):
    code = 0
    while word:
        leading = word.bit_length() - 1
        entry = pivots.get(leading)
        if entry is None:
            return None
        pivot, combo = entry
        word ^= pivot
        code ^= combo
    return code


def encode_index(path, all_pivots):
    with path.open("xb") as stream:
        stream.write(HEADER.pack(MAGIC, DOMAIN, N, DIM))
        for s in range(DOMAIN):
            pivots = all_pivots[s]
            stream.write(bytes((len(pivots),)))
            for leading in sorted(pivots, reverse=True):
                word, coefficient = pivots[leading]
                stream.write(bytes((leading,)))
                stream.write(word.to_bytes(17, "little"))
                stream.write(coefficient.to_bytes(2, "little"))
    return path.stat().st_size


def inverse(onb, basis, all_pivots, valid_set, s, z_mask):
    if s <= 0 or s >= DOMAIN or z_mask <= 0 or z_mask >= (1 << N):
        return None
    z = onb.fromCoords(z_mask)
    az = aval(onb, z)
    if az == 0:
        return None
    seed_sum = phi_from_code(onb, basis, s)
    right = onb.sqr(onb.add(seed_sum, z))
    quotient = onb.mul(right, onb.inv(az))
    code = solve(all_pivots[s], onb.toCoords(quotient))
    if code is None:
        return None
    partner = code ^ s
    if code not in valid_set or partner not in valid_set or code == partner:
        return None
    return tuple(sorted((code, partner)))


def inverse_all_sums(onb, all_pivots, valid_set, seed_squares, z_mask):
    z = onb.fromCoords(z_mask)
    az = aval(onb, z)
    if az == 0:
        return []
    inverse_az = onb.inv(az)
    z_squared = onb.sqr(z)
    pairs = []
    for s in range(1, DOMAIN):
        right = onb.mul(onb.add(seed_squares[s], z_squared), inverse_az)
        code = solve(all_pivots[s], onb.toCoords(right))
        if code is None:
            continue
        partner = code ^ s
        if code in valid_set and partner in valid_set and code != partner:
            pairs.append(tuple(sorted((code, partner))))
    return sorted(set(pairs))


def phi_of(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def check_group_output(onb, curve, basis, pair, z_mask):
    a, b = pair
    points = []
    for code in (a, b):
        phi = phi_from_code(onb, basis, code)
        point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
        if point is None:
            raise ValueError("accepted pair lacks point lift")
        points.append(point)
    plus = phi_of(onb, curve.add(points[0], points[1]))
    minus = phi_of(onb, curve.add(points[0], curve.neg(points[1])))
    if z_mask not in (plus, minus):
        raise ValueError("linear inverse accepted an incorrect S3 root")
    return {"plus": plus, "minus": minus}


def main():
    result_path = HERE / "result.json"
    index_path = HERE / "pivots.bin"
    valid_path = HERE / "valid_codes.json"
    if any(path.exists() for path in (result_path, index_path, valid_path,
                                      HERE / "failure.json")):
        raise FileExistsError("preserve prior d13 same-rotation inverse run")
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    geometry_path = STATIC / "d13_exact_geometry_v1.json"
    manifest_path = PIPELINE / "d13_m12_candidate_manifest_v1.json"
    if (protocol["status"] != "FROZEN" or
            protocol["source_sha256"]["geometry"] != sha(geometry_path) or
            protocol["source_sha256"]["manifest"] != sha(manifest_path) or
            protocol["source_sha256"]["run"] != sha(Path(__file__)) or
            protocol["source_sha256"]["field"] != sha(CODEGEN / "field.py") or
            protocol["source_sha256"]["curves"] != sha(CODEGEN / "curves.py") or
            protocol["source_sha256"]["runtime"] != sha(HERE / "runtime_info.json") or
            json.loads((HERE / "runtime_info.json").read_text())["status"] != "verified"):
        raise ValueError("frozen source or Sage runtime changed")
    geometry = json.loads(geometry_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    curve_record = manifest["candidate_record"]["curve"]
    if (geometry["domain"]["dimension"] != DIM or
            curve_record["subgroup_order"] != 680564733841876926932320129493409985129 or
            geometry["factor_base"]["distinct_nonidentity_signed_subgroup_options_per_position"] != 4134):
        raise ValueError("exact N131 d13 geometry changed")
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    total_start = time.monotonic_ns()

    def guard(stage):
        elapsed = time.monotonic_ns() - total_start
        rss = peak_rss()
        if (elapsed <= protocol["total_wall_cap_seconds"] * 1_000_000_000 and
                rss <= protocol["rss_cap_bytes"]):
            return
        failure = {"kind": "n131_d13_same_rotation_pair_inverse_cap",
                   "status": "CENSORED_TIME" if elapsed >
                   protocol["total_wall_cap_seconds"] * 1_000_000_000
                   else "CENSORED_MEMORY",
                   "stage": stage, "elapsed_wall_ns": elapsed,
                   "peak_process_rss_bytes": rss,
                   "source_sha256": {"protocol": sha(protocol_path),
                                     "run": sha(Path(__file__))}}
        (HERE / "failure.json").write_text(json.dumps(failure, indent=2,
                                                       sort_keys=True) + "\n")
        raise RuntimeError(failure["status"])
    basis = [int(value, 16)
             for value in geometry["domain"]["basis_coordinate_masks_hex"]]
    if len(basis) != DIM or onb.one() in [phi_from_code(onb, basis, s)
                                         for s in range(1, DOMAIN)]:
        raise ValueError("d13 source basis contains field one")

    geometry_start = time.monotonic_ns()
    valid = []
    for code in range(1, DOMAIN):
        if code % 256 == 0:
            guard("valid_selector_enumeration")
        phi = phi_from_code(onb, basis, code)
        x = onb.add(onb.inv(phi), onb.one())
        point = curve.pointFromX(x)
        if point is not None and curve.mul(point, 4) is not None:
            valid.append(code)
    if len(valid) != 4134:
        raise ValueError("valid d13 selector count changed")
    valid_set = set(valid)
    pair_counts = [0] * DOMAIN
    for s in range(1, DOMAIN):
        if s % 256 == 0:
            guard("seed_sum_pair_counts")
        pair_counts[s] = sum(a < (a ^ s) and (a ^ s) in valid_set for a in valid)
    if sum(pair_counts) != len(valid) * (len(valid) - 1) // 2:
        raise ValueError("seed-sum buckets omit an unordered valid pair")
    geometry_ns = time.monotonic_ns() - geometry_start

    index_start = time.monotonic_ns()
    abase = [aval(onb, onb.fromCoords(mask)) for mask in basis]
    all_pivots = [{}]
    seed_squares = [0]
    rank_histogram = {}
    kernel_misses = 0
    for s in range(1, DOMAIN):
        if s % 128 == 0:
            guard("cached_pivot_index")
        seed_sum = phi_from_code(onb, basis, s)
        seed_squares.append(onb.sqr(seed_sum))
        as_ = aval(onb, seed_sum)
        columns = [onb.toCoords(onb.add(onb.sqr(a), onb.mul(as_, a)))
                   for a in abase]
        pivots, kernel = echelon(columns)
        rank_histogram[len(pivots)] = rank_histogram.get(len(pivots), 0) + 1
        if kernel != [s]:
            kernel_misses += 1
        all_pivots.append(pivots)
    if rank_histogram != {12: DOMAIN - 1} or kernel_misses:
        raise ValueError("known-sum map lost its exact swap-only kernel")
    index_bytes = encode_index(index_path, all_pivots)
    index_ns = time.monotonic_ns() - index_start
    valid_path.write_text(json.dumps(valid, separators=(",", ":")) + "\n")

    control_start = time.monotonic_ns()
    rng = random.Random(protocol["control_seed"])
    positives = []
    while len(positives) < protocol["positive_controls"]:
        guard("positive_controls")
        a, b = rng.sample(valid, 2)
        pair = tuple(sorted((a, b)))
        p = []
        for code in pair:
            phi = phi_from_code(onb, basis, code)
            p.append(curve.pointFromX(onb.add(onb.inv(phi), onb.one())))
        for signed in (p[1], curve.neg(p[1])):
            z_mask = phi_of(onb, curve.add(p[0], signed))
            if z_mask is None:
                continue
            recovered = inverse(onb, basis, all_pivots, valid_set,
                                pair[0] ^ pair[1], z_mask)
            if recovered != pair:
                raise ValueError("positive known-sum pair inverse failed")
            check_group_output(onb, curve, basis, pair, z_mask)
            positives.append({"sum_code": pair[0] ^ pair[1],
                              "codes": list(pair), "output_phi_mask": z_mask})
            if len(positives) >= protocol["positive_controls"]:
                break
    negative_hits = 0
    for _ in range(protocol["negative_controls"]):
        guard("negative_controls")
        s = rng.randrange(1, DOMAIN)
        z_mask = rng.randrange(1, 1 << N)
        pair = inverse(onb, basis, all_pivots, valid_set, s, z_mask)
        if pair is not None:
            negative_hits += 1
            check_group_output(onb, curve, basis, pair, z_mask)
    guard("full_pair_inverse_controls")
    full_scan_positive = positives[0]
    full_scan_positive_start = time.monotonic_ns()
    positive_hits = inverse_all_sums(onb, all_pivots, valid_set,
                                     seed_squares,
                                     full_scan_positive["output_phi_mask"])
    full_scan_positive_ns = time.monotonic_ns() - full_scan_positive_start
    if tuple(full_scan_positive["codes"]) not in positive_hits:
        raise ValueError("unconditioned pair inverse lost a positive descriptor")
    for pair in positive_hits:
        check_group_output(onb, curve, basis, pair,
                           full_scan_positive["output_phi_mask"])
    guard("full_pair_inverse_negative")
    full_scan_negative_mask = rng.randrange(1, 1 << N)
    full_scan_negative_start = time.monotonic_ns()
    negative_pairs = inverse_all_sums(onb, all_pivots, valid_set,
                                      seed_squares, full_scan_negative_mask)
    full_scan_negative_ns = time.monotonic_ns() - full_scan_negative_start
    for pair in negative_pairs:
        check_group_output(onb, curve, basis, pair, full_scan_negative_mask)
    control_ns = time.monotonic_ns() - control_start
    guard("terminal_receipt")

    receipt = {"kind": "n131_d13_same_rotation_known_sum_pair_inverse",
               "status": "PASS_EXACT_PAIR_INVERSE_CONTROLS",
               "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "run_id": None,
               "curve_id": geometry["curve_id"],
               "valid_selector_count": len(valid),
               "rotation_schedule": protocol["rotation_schedule"],
               "unordered_distinct_pair_descriptors": sum(pair_counts),
               "nonempty_seed_sum_buckets": sum(value > 0 for value in pair_counts),
               "pair_count_min_positive_bucket": min(value for value in pair_counts[1:] if value),
               "pair_count_max_bucket": max(pair_counts),
               "pair_count_zero_buckets": sum(value == 0 for value in pair_counts[1:]),
               "fixed_sum_map_rank_histogram": rank_histogram,
               "fixed_sum_kernel_misses": kernel_misses,
               "cached_pivot_index_bytes": index_bytes,
               "geometry_wall_ns": geometry_ns,
               "index_wall_ns": index_ns,
               "control_wall_ns": control_ns,
               "peak_process_rss_bytes": peak_rss(),
               "positive_controls": positives,
               "negative_control_count": protocol["negative_controls"],
               "negative_control_hits": negative_hits,
               "full_inverse_positive_output_phi_mask":
               full_scan_positive["output_phi_mask"],
               "full_inverse_positive_pairs": [list(pair) for pair in positive_hits],
               "full_inverse_positive_wall_ns": full_scan_positive_ns,
               "full_inverse_negative_output_phi_mask": full_scan_negative_mask,
               "full_inverse_negative_pairs": [list(pair) for pair in negative_pairs],
               "full_inverse_negative_wall_ns": full_scan_negative_ns,
               "source_sha256": {"protocol": sha(protocol_path),
                                 "geometry": sha(geometry_path),
                                 "manifest": sha(manifest_path),
                                 "run": sha(Path(__file__)),
                                 "runtime": sha(HERE / "runtime_info.json"),
                                 "valid_codes": sha(valid_path),
                                 "pivots": sha(index_path)}}
    result_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "valid_selector_count",
                       "unordered_distinct_pair_descriptors",
                       "cached_pivot_index_bytes", "peak_process_rss_bytes")}))


if __name__ == "__main__":
    main()
