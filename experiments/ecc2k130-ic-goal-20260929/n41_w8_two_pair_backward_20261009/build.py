#!/usr/bin/env python3
"""Exact two-pair backward residual table for the frozen N41 public target."""

import hashlib
import json
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PREVIOUS = GOAL / "n41_w8_fixed_sum_backward_20261009"
sys.path.insert(0, str(PREVIOUS))
import run as previous

GEOMETRY = PREVIOUS / "geometry.json"
PUBLIC = GOAL / "n41_adjacent_pairpair/public_target.json"
WITNESS = GOAL / "n41_w8_fixed_sum_pair_blocks_20261009/six_block_join/result.json"
WITNESS_AUDIT = GOAL / "n41_w8_fixed_sum_pair_blocks_20261009/six_block_join/audit.json"
SOURCE_MODULE = GOAL / "run_n41_disjoint_s5_sat.py"
PROPOSAL_ID = "Q20261009181500"
LIMIT_NS = 600_000_000_000
LIMIT_RSS = 4 * 1024**3
RECORD_BYTES = 15  # two 41-bit coordinates and three one-byte labels


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return [HERE / "build.py", HERE / "audit.py", GEOMETRY, PUBLIC,
            WITNESS, WITNESS_AUDIT, SOURCE_MODULE, PREVIOUS / "run.py"]


def verify_freeze():
    protocol = json.loads((HERE / "protocol.json").read_text())
    actual = {str(path): sha(path) for path in source_paths()}
    if protocol["source_sha256"] != actual or protocol["time_cap_ns"] != LIMIT_NS:
        raise ValueError("frozen source or cap changed")
    return protocol


def encode(point, target_index, state4, state5):
    return (point[0].to_bytes(6, "little") + point[1].to_bytes(6, "little") +
            bytes((target_index, state4, state5)))


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def main():
    if (HERE / "result.json").exists() or (HERE / "table.bin").exists():
        raise FileExistsError("preserve first frozen run")
    protocol = verify_freeze()
    setup_start = time.monotonic_ns()
    geometry = json.loads(GEOMETRY.read_text())
    if geometry["curve_id"] != "EC1N41Ckb1h7d5e80d3c4d0":
        raise ValueError("curve changed")
    states4 = geometry["blocks"][4]["states"]
    states5 = geometry["blocks"][5]["states"]
    valid_pairs = [(i, j) for i, left in enumerate(states4)
                   for j, right in enumerate(states5)
                   if len(set(left["columns"] + right["columns"])) == 4]
    field = previous.base.Field(41, [0, 3])
    curve = previous.base.Curve(field, 0)
    setup_ns = time.monotonic_ns() - setup_start
    online_start = time.monotonic_ns()
    q, raw_targets, _ = previous.target_data(field, curve, geometry, "public")
    preimage_ns = time.monotonic_ns() - online_start
    witness_indices = json.loads(WITNESS.read_text())["witness"]
    witness_states = [geometry["blocks"][k]["states"][index]
                      for k, index in enumerate(witness_indices)]
    first4 = None
    full = None
    for k, state in enumerate(witness_states):
        full = curve.add(full, tuple(state["raw_sum"]))
        if k == 3:
            first4 = full
    if full not in raw_targets or curve.mul(4, full) != q:
        raise ValueError("saved public relation failed preflight")
    witness_branch = raw_targets.index(full)
    witness_key = (witness_branch, witness_indices[4], witness_indices[5])
    records = bytearray()
    group_multiplicity = {}
    x_values = set()
    exceptional = {"identity": 0, "x_one": 0}
    witness_offset = None
    checks = 0
    status = "EXACT_TWO_PAIR_DOMAIN"
    for branch, target in enumerate(raw_targets):
        for i, state4 in enumerate(states4):
            partial = curve.add(target, curve.neg(tuple(state4["raw_sum"])))
            for j, state5 in enumerate(states5):
                if len(set(state4["columns"] + state5["columns"])) != 4:
                    continue
                residual = curve.add(partial, curve.neg(tuple(state5["raw_sum"])))
                checks += 1
                if residual is None:
                    exceptional["identity"] += 1
                    continue
                if residual[0] == 1:
                    exceptional["x_one"] += 1
                    continue
                if (curve.add(curve.add(residual, tuple(state4["raw_sum"])),
                              tuple(state5["raw_sum"])) != target):
                    raise ValueError("backward point failed exact group replay")
                group_multiplicity[residual] = group_multiplicity.get(residual, 0) + 1
                x_values.add(residual[0])
                offset = len(records) // RECORD_BYTES
                records.extend(encode(residual, branch, i, j))
                if (branch, i, j) == witness_key:
                    if residual != first4:
                        raise ValueError("known first-four partial sum missing")
                    witness_offset = offset
                if checks % 4096 == 0:
                    if time.monotonic_ns() - online_start > LIMIT_NS:
                        status = "ONLINE_TIME_CAP"
                        break
                    if rss_bytes() > LIMIT_RSS:
                        status = "MEMORY_CAP"
                        break
            if status != "EXACT_TWO_PAIR_DOMAIN":
                break
        if status != "EXACT_TWO_PAIR_DOMAIN":
            break
    table_ns = time.monotonic_ns() - online_start - preimage_ns
    (HERE / "table.bin").write_bytes(records)
    result = {"status": status, "proposal_id": PROPOSAL_ID,
              "candidate_id": None, "run_id": None,
              "curve_id": geometry["curve_id"], "public_target_q": list(q),
              "raw_target_preimages": [list(point) for point in raw_targets],
              "raw_target_count": len(raw_targets),
              "states_per_backward_block": [len(states4), len(states5)],
              "valid_two_block_state_pairs": len(valid_pairs),
              "cross_block_column_rejects": len(states4)*len(states5)-len(valid_pairs),
              "full_labeled_state_count": len(raw_targets)*len(states4)*len(states5),
              "checked_valid_labeled_states": checks,
              "exceptional_residuals": exceptional,
              "stored_labeled_residuals": len(records)//RECORD_BYTES,
              "distinct_residual_group_points": len(group_multiplicity),
              "distinct_residual_x_coordinates": len(x_values),
              "group_collision_excess": len(records)//RECORD_BYTES-len(group_multiplicity),
              "maximum_group_multiplicity": max(group_multiplicity.values(), default=0),
              "witness_branch": witness_branch,
              "witness_state_indices": witness_indices,
              "witness_table_offset": witness_offset,
              "witness_first_four_point": list(first4),
              "record_bytes": RECORD_BYTES, "table_sha256": sha(HERE / "table.bin"),
              "setup_ns": setup_ns, "target_preimage_ns": preimage_ns,
              "target_dependent_table_ns": table_ns,
              "charged_target_dependent_wall_ns": time.monotonic_ns()-online_start,
              "peak_rss_bytes": rss_bytes(),
              "protocol_sha256": sha(HERE / "protocol.json"),
              "source_sha256": protocol["source_sha256"]}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "stored_labeled_residuals",
                       "distinct_residual_group_points", "distinct_residual_x_coordinates",
                       "group_collision_excess", "witness_table_offset",
                       "charged_target_dependent_wall_ns", "peak_rss_bytes")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
