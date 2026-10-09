#!/usr/bin/env sage -python
"""Build exact target-conditioned two-leaf suffix support for N41."""

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
BASE = GOAL / "n41_phi_second_link_control_20261009"
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")
sys.path.insert(0, str(CODEGEN))
import curves
import field

N, DIM, M = 41, 6, 12
PARTIAL9_START = 2 + M * DIM + 9 * N


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def leaf(onb, curve, basis, code, position):
    mask = 0
    for bit, value in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= value
    phi = onb.frob(onb.fromCoords(mask), position)
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("valid leaf code lost a point")
    return point


def phi_mask(onb, point):
    if point is None or point[0] == onb.one():
        return None
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def main():
    paths = [HERE / name for name in ("suffix_masks.json", "guided.xcnf",
                                       "protocol.json")]
    if any(path.exists() for path in paths):
        raise FileExistsError("preserve prior suffix index and formula")
    previous_protocol = BASE / "protocol.json"
    previous_table = BASE / "table.json"
    previous_audit = BASE / "audit.json"
    runtime = HERE / "runtime_info.json"
    protocol = json.loads(previous_protocol.read_text())
    table = json.loads(previous_table.read_text())
    audit = json.loads(previous_audit.read_text())
    if (json.loads(runtime.read_text())["status"] != "verified" or
            protocol["target_count"] != 1 or protocol["batch"] is not False or
            protocol["source_sha256"]["table"] != sha(previous_table) or
            audit["source_sha256"]["protocol"] != sha(previous_protocol) or
            table["status"] != "FROZEN" or len(table["valid_codes"]) != 30):
        raise ValueError("frozen N41 public-target control changed")
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    endpoint = tuple(onb.fromCoords(value) for value in
                     protocol["endpoint_coordinates"])
    target = tuple(onb.fromCoords(value) for value in
                   protocol["target_coordinates"])
    if curve.mul(endpoint, 4) != target:
        raise ValueError("endpoint does not project to public target")
    codes = table["valid_codes"]
    basis = table["basis_coordinate_masks"]
    options10 = []
    options11 = []
    for position, output in ((10, options10), (11, options11)):
        for code in codes:
            point = leaf(onb, curve, basis, code, position)
            output.extend((point, curve.neg(point)))
    if len(options10) != 60 or len(options11) != 60:
        raise ValueError("suffix signed domains changed")
    reusable_began = time.monotonic()
    pair_sums = [curve.add(left, right) for left in options10
                 for right in options11]
    reusable_seconds = time.monotonic() - reusable_began
    if len(pair_sums) != 3600:
        raise ValueError("suffix pair index incomplete")
    target_began = time.monotonic()
    masks = set()
    exceptional = 0
    for pair in pair_sums:
        residual = curve.add(endpoint, curve.neg(pair))
        mask = phi_mask(onb, residual)
        if mask is None:
            exceptional += 1
        else:
            masks.add(mask)
    masks = sorted(masks)
    if not masks or any(not 0 < mask < (1 << N) for mask in masks):
        raise ValueError("empty or invalid target-conditioned suffix support")
    suffix = {
        "kind": "n41_phi_target_conditioned_two_leaf_suffix_support",
        "status": "FROZEN_ENUMERATION", "proposal_id": "Q20261009150000",
        "candidate_id": None, "run_id": None, "target_count": 1,
        "suffix_positions": [10, 11],
        "signed_options_per_position": 60,
        "enumerated_signed_pairs": len(pair_sums),
        "nonfinite_residual_cases": exceptional,
        "distinct_finite_partial9_masks": len(masks),
        "masks": masks,
        "endpoint_sign_rule": "one endpoint E suffices for x-only partial9; negating a valid -E suffix equation flips both leaf signs and preserves x",
        "source_sha256": {"previous_protocol": sha(previous_protocol),
                          "previous_table": sha(previous_table),
                          "previous_audit": sha(previous_audit),
                          "runtime": sha(runtime), "builder": sha(Path(__file__))},
    }
    paths[0].write_text(json.dumps(suffix, indent=2, sort_keys=True) + "\n")
    source = BASE / "lookup.xcnf"
    destination = paths[1]
    with source.open("rt", encoding="ascii") as src, destination.open(
            "x", encoding="ascii") as dst:
        header = src.readline().split()
        if header != ["p", "cnf", "34365", "54513"]:
            raise ValueError("lookup input XCNF changed")
        old_vars, old_records = int(header[2]), int(header[3])
        dst.write(f"p cnf {old_vars + len(masks)} "
                  f"{old_records + len(masks) * N + 1}\n")
        for line in src:
            dst.write(line)
        selectors = []
        for index, mask in enumerate(masks):
            selector = old_vars + index + 1
            selectors.append(selector)
            for bit in range(N):
                variable = PARTIAL9_START + bit
                literal = variable if (mask >> bit) & 1 else -variable
                dst.write(f"{-selector} {literal} 0\n")
        dst.write(" ".join(str(value) for value in selectors) + " 0\n")
    target_seconds = time.monotonic() - target_began
    frozen = {
        "kind": "n41_phi_suffix2_target_guided_public_query",
        "status": "FROZEN", "proposal_id": suffix["proposal_id"],
        "candidate_id": None, "run_id": None, "curve_id": None,
        "workload_id": None, "target_count": 1, "batch": False,
        "target_coordinates": protocol["target_coordinates"],
        "endpoint_coordinates": protocol["endpoint_coordinates"],
        "first_link_leaf_codes": protocol["leaf_codes"],
        "first_link_root_mask": protocol["first_root_mask"],
        "reusable_pair_sum_seconds": reusable_seconds,
        "target_conditioned_build_seconds": target_seconds,
        "solver": str(SOLVER),
        "solver_flags": protocol["solver_flags"],
        "wall_cap_seconds": 240,
        "combined_rss_cap_bytes": 2147483648,
        "source_sha256": {"previous_protocol": sha(previous_protocol),
                          "previous_table": sha(previous_table),
                          "previous_audit": sha(previous_audit),
                          "previous_lookup": sha(source),
                          "suffix": sha(paths[0]), "guided": sha(destination),
                          "runtime": sha(runtime), "solver": sha(SOLVER),
                          "builder": sha(Path(__file__))},
        "accounting_boundary": "target-independent leaf options and pair sums precede online interval; target-conditioned residuals and guided encoding are charged, followed by solver and replay",
    }
    paths[2].write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "suffix_masks": len(masks),
                      "exceptional": exceptional,
                      "reusable_seconds": reusable_seconds,
                      "target_conditioned_seconds": target_seconds}))


if __name__ == "__main__":
    main()
