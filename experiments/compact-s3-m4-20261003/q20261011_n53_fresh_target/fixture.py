#!/usr/bin/env python3
"""Freeze one fresh N53 public target and a separate scalar replay fixture."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ecc2k130/codegen"))
import curves  # noqa: E402
import field  # noqa: E402


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    assert not (HERE / "public_target.json").exists()
    assert not (HERE / "target_fixture.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    r = protocol["subgroup_order"]
    seed = protocol["target_fixture"]["seed_text"].encode()
    limit = (1 << 256) // (r - 1) * (r - 1)
    counter = 0
    while True:
        candidate = int.from_bytes(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest(), "big")
        if candidate < limit:
            scalar = candidate % (r - 1) + 1
            break
        counter += 1
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    generator = tuple(protocol["generator_onb_xy"])
    assert curve.onCurve(generator) and curve.mul(generator, r) is None
    target = curve.mul(generator, scalar)
    assert target is not None and target != generator and curve.mul(target, r) is None
    workload_record = {"curve_id": protocol["curve_id"],
                       "subgroup_order": r, "target_onb_xy": list(target),
                       "input_law": protocol["target_fixture"]["input_law"],
                       "seed_text": protocol["target_fixture"]["seed_text"],
                       "target_count": 1, "online_cache_policy": "precomputed_factor_base_logs"}
    workload_id = digest(workload_record)[:12]
    public = {"curve_id": protocol["curve_id"], "subgroup_order": r,
              "generator_onb_xy": list(generator), "target_onb_xy": list(target),
              "workload_id": workload_id}
    fixture = {"proposal_id": "Q1461", "curve_id": protocol["curve_id"],
               "input_law": protocol["target_fixture"]["input_law"],
               "seed_text": protocol["target_fixture"]["seed_text"],
               "counter": counter, "scalar": scalar,
               "workload_record": workload_record,
               "workload_hash_full": digest(workload_record),
               "workload_id": workload_id,
               "public_target_sha256": digest(public)}
    (HERE / "public_target.json").write_text(json.dumps(public, indent=2,
                                                        sort_keys=True) + "\n")
    (HERE / "target_fixture.json").write_text(json.dumps(fixture, indent=2,
                                                         sort_keys=True) + "\n")
    print("FROZEN Q1461", workload_id, "public target", target)


if __name__ == "__main__":
    main()
