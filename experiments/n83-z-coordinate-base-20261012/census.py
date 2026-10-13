#!/usr/bin/env python3
"""Exact N83 trace-zero z-base enumeration in the checked Sage runtime."""

import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "census.json"
ROOTS = HERE / "roots.bin"
KEYS = HERE / "keys.bin"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def field_bits(value):
    return sum(int(c) << i for i, c in enumerate(value.polynomial().list()))


def main():
    assert not any(path.exists() for path in (OUTPUT, ROOTS, KEYS)), "refusing to overwrite evidence"
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["curve_id"] == "EC1N83Ckb1h876c2921cb64"
    assert protocol["subgroup_order"] == 2417851639230796216685689
    R = PolynomialRing(GF(2), "t")
    t = R.gen()
    modulus = t**83 + t**7 + t**4 + t**2 + 1
    assert modulus.is_irreducible()
    field = GF(2**83, name="a", modulus=modulus)
    T = field.gen()
    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    zero = curve(0)
    poly = PolynomialRing(field, "X")
    X = poly.gen()
    basis = [T**i for i in range(1, 12)]
    assert len(set(basis)) == 11
    assert all(int(b.trace()) == 0 for b in basis)
    z_values = [field(0)]
    for b in basis:
        z_values += [z + b for z in z_values]
    assert len(z_values) == len(set(z_values)) == 2048
    start = time.monotonic()
    root_hist = Counter()
    all_roots = []
    keys = set()
    identities = 0
    duplicates = 0
    n = 83
    for i, z in enumerate(z_values):
        assert int(z.trace()) == 0
        roots = sorted((r for r, mult in (X**3 + z*X**2 + 1).roots()), key=field_bits)
        root_hist[len(roots)] += 1
        assert len(roots) in (0, 1, 3)
        for x in roots:
            assert x != 0 and x**3 + z*x**2 + 1 == 0
            assert x + x**-2 == z
            p = curve.lift_x(x)
            assert p[1]**2 + x*p[1] == x**3 + 1
            q = protocol["cofactor"] * p
            all_roots.append(field_bits(x))
            if q == zero:
                identities += 1
                continue
            assert protocol["subgroup_order"] * q == zero
            xx, yy = q[0], q[1]
            best = None
            for _ in range(n):
                candidate = (field_bits(xx) << n) | min(field_bits(yy), field_bits(yy + xx))
                best = candidate if best is None else min(best, candidate)
                xx, yy = xx**2, yy**2
            if best in keys:
                duplicates += 1
            keys.add(best)
        if (i + 1) % 256 == 0:
            print(json.dumps({"z_checked": i + 1, "roots": len(all_roots), "K": len(keys), "elapsed_s": round(time.monotonic() - start, 3)}), flush=True)
    roots_blob = b"".join(v.to_bytes(11, "little") for v in sorted(all_roots))
    keys_blob = b"".join(v.to_bytes(21, "little") for v in sorted(keys))
    ROOTS.write_bytes(roots_blob)
    KEYS.write_bytes(keys_blob)
    report = {
        "kind": "n83_trace_zero_z_coordinate_base_census_v1",
        "status": "complete",
        "protocol_sha256": digest(PROTOCOL.read_bytes()),
        "source_sha256": digest(Path(__file__).read_bytes()),
        "root_histogram": {str(k): root_hist[k] for k in (0, 1, 3)},
        "raw_x_roots": len(all_roots),
        "subgroup_identities": identities,
        "signed_frobenius_seed_duplicates": duplicates,
        "effective_columns_K": len(keys),
        "actual_subgroup_points_B": 166 * len(keys),
        "roots_file_sha256": digest(roots_blob),
        "keys_file_sha256": digest(keys_blob),
        "elapsed_seconds": time.monotonic() - start,
        "scope": "exact factor-base geometry only; decomposition encoding and target recovery unmeasured",
    }
    OUTPUT.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
