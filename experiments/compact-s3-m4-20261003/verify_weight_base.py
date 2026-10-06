#!/usr/bin/env python3
"""Check the compressed factor-base set and a deterministic subgroup sample."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import random
from pathlib import Path

from run_probe import curve_record, curves, field, sha


def verify(path, sample_size=32):
    with gzip.open(path, "rt") as source:
        record = json.load(source)
    n = record["field"]["n"]
    source_path, candidate = curve_record(n)
    assert record["field"] == candidate["field"]
    assert record["curve"] == candidate["curve"]
    assert record["isogeny"] == "none"
    fb = record["factor_base"]
    packed = base64.b64decode(fb["packed_canonical_x_keys_base64"],
                              validate=True)
    width = (n + 7) // 8
    assert len(packed) == width * fb["signed_frobenius_columns"]
    assert hashlib.sha256(packed).hexdigest() == fb["enumerated_set_sha256"]
    keys = [int.from_bytes(packed[i:i + width], "little")
            for i in range(0, len(packed), width)]
    assert keys == sorted(set(keys))
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    lengths = []
    for key in keys:
        first = onb.fromCoords(key)
        x = first
        members = []
        while True:
            members.append(onb.toCoords(x))
            x = onb.frob(x, 1)
            if x == first:
                break
            assert len(members) < n
        assert key == min(members)
        lengths.append(len(members))
    assert lengths == fb["orbit_lengths"]
    assert 2 * sum(lengths) == fb[
        "actual_usable_points_B_before_folding"]
    rng = random.Random(13015383 + n)
    indices = sorted(set([0, len(keys) - 1] + [rng.randrange(len(keys))
                                                for _ in range(sample_size)]))
    order = int(record["curve"]["subgroup_order"])
    for index in indices:
        point = curve.pointFromX(onb.fromCoords(keys[index]))
        assert point is not None and curve.onCurve(point)
        assert curve.mul(point, order) is None
    return {
        "kind": "normal_weight_orbit_factor_base_verification",
        "pass": True,
        "curve_id": record["curve"]["curve_id"],
        "n": n,
        "B": fb["actual_usable_points_B_before_folding"],
        "columns": len(keys),
        "enumerated_set_sha256": fb["enumerated_set_sha256"],
        "all_canonical_keys_and_orbit_lengths_checked": len(keys),
        "subgroup_sample_keys_checked": len(indices),
        "base_archive_sha256": sha(path),
        "curve_manifest_sha256": sha(source_path),
        "source_sha256": sha(Path(__file__)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    result = verify(args.base)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("n", "B", "columns",
                                           "subgroup_sample_keys_checked")}))


if __name__ == "__main__":
    main()
