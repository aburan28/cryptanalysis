#!/usr/bin/env python3
"""Enumerate a cofactor-projected normal-weight base by Frobenius orbits."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import itertools
import json
import resource
import time
from pathlib import Path

from chain_s3 import square_destinations
from run_probe import curve_record, sha, curves, field

HERE = Path(__file__).resolve().parent


def permute(mask, positions):
    out = 0
    while mask:
        bit = mask & -mask
        out |= 1 << positions[bit.bit_length() - 1]
        mask ^= bit
    return out


def orbit(mask, positions):
    current = mask
    result = []
    while True:
        result.append(current)
        current = permute(current, positions)
        if current == mask:
            return result
        assert len(result) < len(positions)


def enumerate_base(n, weight):
    manifest_path, candidate = curve_record(n)
    onb = field.Onb(n)
    curve = curves.Curve(onb)
    cofactor = int(candidate["curve"]["cofactor"])
    positions = square_destinations(onb)
    seen = set()
    keys = {}
    visited_x = rational_x = raw_orbits = rational_orbits = 0
    projected_identity_orbits = projected_duplicate_orbits = 0
    began = time.perf_counter()
    for size in range(1, weight + 1):
        for subset in itertools.combinations(range(n), size):
            mask = sum(1 << i for i in subset)
            if mask in seen:
                continue
            raw_orbit = orbit(mask, positions)
            seen.update(raw_orbit)
            visited_x += len(raw_orbit)
            raw_orbits += 1
            point = curve.pointFromX(onb.fromCoords(mask))
            if point is None:
                continue
            rational_orbits += 1
            rational_x += len(raw_orbit)
            projected = curve.mul(point, cofactor)
            if projected is None:
                projected_identity_orbits += 1
                continue
            projected_x = onb.toCoords(projected[0])
            projected_orbit = orbit(projected_x, positions)
            canonical = min(projected_orbit)
            if canonical in keys:
                assert keys[canonical] == len(projected_orbit)
                projected_duplicate_orbits += 1
            else:
                keys[canonical] = len(projected_orbit)
    assert visited_x == sum(__import__("math").comb(n, i)
                            for i in range(1, weight + 1))
    assert all(length <= n for length in keys.values())
    packed_width = (n + 7) // 8
    packed = b"".join(key.to_bytes(packed_width, "little")
                      for key in sorted(keys))
    actual_b = 2 * sum(keys.values())
    result = {
        "kind": "normal_weight_cofactor_projected_orbit_factor_base",
        "schema_version": 1,
        "proposal_id": {53: "Q1301", 83: "Q1302"}[n],
        "candidate_id": None,
        "field": candidate["field"],
        "curve": candidate["curve"],
        "isogeny": "none",
        "endomorphism": candidate["endomorphism"],
        "factor_base": {
            "construction": "all rational nonzero x of normal-basis weight at most w; both curve lifts; project by the exact curve cofactor; discard identity and deduplicate",
            "normal_basis_weight_bound": weight,
            "cofactor_projection": cofactor,
            "nominal_x_mask_count": visited_x,
            "geometric_rational_x_count": rational_x,
            "geometric_point_count_before_projection": 2 * rational_x,
            "actual_usable_points_B_before_folding": actual_b,
            "sign_frobenius_quotient": "{plus/minus sigma^j(P), j=0..n-1}; canonical key is smallest normal-basis x coordinate",
            "signed_frobenius_columns": len(keys),
            "enumerated_set_encoding": f"sorted canonical x-coordinate keys, {packed_width}-byte little-endian; expand by the recorded signed Frobenius orbit length",
            "enumerated_set_sha256": hashlib.sha256(packed).hexdigest(),
            "packed_canonical_x_keys_base64": base64.b64encode(packed).decode("ascii"),
            "orbit_lengths": [keys[key] for key in sorted(keys)],
        },
        "enumeration": {
            "raw_frobenius_orbits": raw_orbits,
            "rational_raw_orbits": rational_orbits,
            "projected_identity_orbits": projected_identity_orbits,
            "projected_duplicate_orbits": projected_duplicate_orbits,
            "elapsed_seconds": time.perf_counter() - began,
            "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "peak_rss_units": "bytes on Darwin, KiB on Linux",
            "source_sha256": sha(Path(__file__)),
            "field_source_sha256": sha(Path(field.__file__)),
            "curve_source_sha256": sha(Path(curves.__file__)),
            "curve_manifest_sha256": sha(manifest_path),
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(53, 83), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    result = enumerate_base(args.n, {53: 3, 83: 4}[args.n])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(result, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    with args.out.open("xb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0,
                           compresslevel=9) as compressed:
            compressed.write(content)
    print(json.dumps({"n": args.n,
                      "B": result["factor_base"][
                          "actual_usable_points_B_before_folding"],
                      "columns": result["factor_base"][
                          "signed_frobenius_columns"],
                      "base_sha256": result["factor_base"][
                          "enumerated_set_sha256"],
                      "elapsed_seconds": result["enumeration"]["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
