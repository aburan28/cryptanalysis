#!/usr/bin/env sage -python
"""Exact affine-span witness for same-rotation N131 d13 pair outputs."""

import hashlib
import json
import random
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PAIR = GOAL / "n131_d13_same_rotation_pairs_20261009"
STATIC = GOAL / "n131_phi_torsion_frobenius_domains_20261005/m12_d13_static"
sys.path.insert(0, str(PAIR))
import run as pair


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_pivot(pivots, row):
    while row:
        bit = row.bit_length() - 1
        if bit not in pivots:
            pivots[bit] = row
            return True
        row ^= pivots[bit]
    return False


def main():
    output = HERE / "result.json"
    if output.exists():
        raise FileExistsError("preserve frozen span run")
    protocol_path = HERE / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    paths = {"producer": HERE / "produce.py",
             "runtime": HERE / "runtime_info.json",
             "geometry": STATIC / "d13_exact_geometry_v1.json",
             "valid_codes": PAIR / "valid_codes.json",
             "pair_result": PAIR / "result.json",
             "pair_source": PAIR / "run.py",
             "field": pair.CODEGEN / "field.py",
             "curves": pair.CODEGEN / "curves.py"}
    if (protocol["status"] != "FROZEN" or
            any(sha(path) != protocol["source_sha256"][key]
                for key, path in paths.items()) or
            json.loads(paths["runtime"].read_text())["status"] != "verified"):
        raise ValueError("frozen source or checked Sage runtime changed")
    geometry = json.loads(paths["geometry"].read_text())
    valid = json.loads(paths["valid_codes"].read_text())
    if (geometry["curve_id"] != protocol["curve_id"] or
            len(valid) != 4134 or len(set(valid)) != len(valid)):
        raise ValueError("d13 geometry or selector set changed")
    basis = [int(value, 16) for value in
             geometry["domain"]["basis_coordinate_masks_hex"]]
    onb = pair.field.Onb(131)
    curve = pair.curves.Curve(onb)
    points = {}

    def point_for(code):
        if code not in points:
            phi = pair.phi_from_code(onb, basis, code)
            point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
            if point is None or curve.mul(point, 4) is None:
                raise ValueError("selector is not a usable subgroup point")
            points[code] = point
        return points[code]

    start = time.monotonic_ns()
    rng = random.Random(protocol["sample_seed"])
    pivots = {}
    witnesses = []
    attempts = 0
    exceptional = 0
    while len(pivots) < 132 and attempts < protocol["max_pair_attempts"]:
        if time.monotonic_ns() - start > protocol["wall_cap_seconds"] * 10**9:
            break
        attempts += 1
        a, b = sorted(rng.sample(valid, 2))
        output_point = curve.add(point_for(a), point_for(b))
        mask = pair.phi_of(onb, output_point)
        if mask is None:
            exceptional += 1
            continue
        if add_pivot(pivots, 1 | (mask << 1)):
            witnesses.append({"codes": [a, b], "output_phi_mask": mask})
    wall_ns = time.monotonic_ns() - start
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    status = ("CENSORED_MEMORY" if rss_bytes > protocol["rss_cap_bytes"] else
              "CENSORED_TIME" if wall_ns > protocol["wall_cap_seconds"] * 10**9 else
              "PASS_FULL_AFFINE_SPAN_CERTIFICATE" if len(pivots) == 132 else
              "BOUNDED_RANK_WITNESS")
    receipt = {"kind": "n131_d13_pair_output_affine_span",
               "status": status, "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "run_id": None,
               "curve_id": protocol["curve_id"],
               "field_coordinate_bits": 131, "augmented_coordinate_bits": 132,
               "pair_attempts": attempts, "exceptional_outputs": exceptional,
               "independent_rows": len(pivots), "witnesses": witnesses,
               "wall_ns": wall_ns, "peak_process_rss_bytes": rss_bytes,
               "source_sha256": {**{key: sha(path) for key, path in paths.items()},
                                 "protocol": sha(protocol_path)}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "pair_attempts", "independent_rows",
                       "wall_ns", "peak_process_rss_bytes")}))


if __name__ == "__main__":
    main()
