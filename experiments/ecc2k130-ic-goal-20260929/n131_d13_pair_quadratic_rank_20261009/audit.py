#!/usr/bin/env sage -python
"""Independently replay a frozen pair sample and its two rank computations."""

import importlib.util
import json
import random
from pathlib import Path

import freeze

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "n131_d13_batch_pair_outputs_20261009/pilot.py"
FNV_OFFSET = 1469598103934665603
FNV_PRIME = 1099511628211
MASK64 = (1 << 64) - 1


def load_pilot():
    spec = importlib.util.spec_from_file_location("frozen_pair_pilot_audit", PILOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def active_features(mask):
    active = [i for i in range(131) if (mask >> i) & 1]
    yield 0
    for i in active:
        yield 1 + i
    for p, i in enumerate(active):
        for j in active[p+1:]:
            yield 1 + 131 + i * (2 * 131 - i - 1) // 2 + j - i - 1


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first independent audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if protocol["source_sha256"] != {
            name: freeze.sha(path) for name, path in freeze.paths().items()}:
        raise ValueError("source identity changed")
    sample = (HERE / "sample.bin").read_bytes()
    sample_result = json.loads((HERE / "sample_result.json").read_text())
    rank = json.loads((HERE / "rank_result.json").read_text())
    second = json.loads((HERE / "audit_rank_result.json").read_text())
    if (len(sample) != protocol["sample_rows"] * 22 or
            freeze.sha(HERE / "sample.bin") != sample_result["sample_sha256"] or
            rank["rows"] != second["rows_read"] or
            rank["rank"] != second["rank"] or
            rank["features"] != second["features"] or
            rank["features"] != protocol["quadratic_features"]):
        raise ValueError("sample or rank receipts disagree")
    valid = json.loads((HERE.parent / "n131_d13_same_rotation_pairs_20261009/valid_codes.json").read_text())
    rng = random.Random(protocol["sample_seed"])
    expected_pairs = []
    for left in range(protocol["left_count"]):
        partners = sorted(rng.sample(range(left + 1, len(valid)),
                                     protocol["partners_per_left"]))
        expected_pairs.extend((left, right) for right in partners)
    digest = FNV_OFFSET
    coordinates = set()
    for row in range(protocol["sample_rows"]):
        offset = 22 * row
        a = int.from_bytes(sample[offset:offset+2], "little")
        b = int.from_bytes(sample[offset+2:offset+4], "little")
        branch = sample[offset+4]
        mask = int.from_bytes(sample[offset+5:offset+22], "little")
        left, right = expected_pairs[row // 2]
        if (a, b, branch) != (valid[left], valid[right], row & 1):
            raise ValueError("sample order or descriptor changed")
        if mask >= 1 << 131:
            raise ValueError("sample coordinate exceeds field")
        coordinates.add(mask)
        if row < 256:
            for feature in active_features(mask):
                digest = ((digest ^ (feature + 1)) * FNV_PRIME) & MASK64
    if (digest != rank["first_256_feature_digest_fnv64"] or
            len(coordinates) != sample_result["distinct_phi_masks"]):
        raise ValueError("quadratic feature map or distinct count differs")
    pilot = load_pilot()
    (_, onb, raw_curve, sage_curve, _, sage_points, raw_points,
     to_pb, sage_int) = pilot.setup()
    rng = random.Random(protocol["sample_seed"] + 1)
    selected = sorted(set(range(32)) | set(rng.sample(range(32,
                                                         protocol["sample_rows"]), 64)))
    for row in selected:
        offset = 22 * row
        mask = int.from_bytes(sample[offset+5:offset+22], "little")
        left, right = expected_pairs[row // 2]
        branch = row & 1
        raw = raw_curve.add(raw_points[left],
                            raw_points[right] if branch == 0
                            else raw_curve.neg(raw_points[right]))
        sage = sage_points[left] + (sage_points[right] if branch == 0
                                   else -sage_points[right])
        if raw is None or sage == sage_curve(0):
            raise ValueError("saved pair reached identity")
        recovered = onb.toCoords(onb.inv(onb.add(raw[0], onb.one())))
        if recovered != mask or to_pb(raw[0]) != sage_int(sage[0]):
            raise ValueError(f"independent pair output mismatch at row {row}")
    result = {"status": "PASS_INDEPENDENT_PAIR_AND_RANK_AUDIT",
              "curve_id": protocol["curve_id"], "proposal_id": protocol["proposal_id"],
              "candidate_id": None, "rows": protocol["sample_rows"],
              "sample_sha256": freeze.sha(HERE / "sample.bin"),
              "rank_m4ri": rank["rank"], "rank_incremental": second["rank"],
              "features": protocol["quadratic_features"],
              "first_256_feature_digest_fnv64": digest,
              "independent_sage_pair_replays": len(selected),
              "rank_full_at_row": second["full_rank_at_row"],
              "source_sha256": protocol["source_sha256"],
              "protocol_sha256": freeze.sha(HERE / "protocol.json")}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "rank": rank["rank"],
                      "features": rank["features"], "sage_replays": len(selected)}))


if __name__ == "__main__":
    main()
