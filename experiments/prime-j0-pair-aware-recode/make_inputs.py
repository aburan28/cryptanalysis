#!/usr/bin/env python3
"""Freeze fresh pairs and generic digests with an independent affine group law."""

import hashlib
import json
import struct
from pathlib import Path


HERE = Path(__file__).resolve().parent
MASK = (1 << 64) - 1
COUNT = 1024
LABEL = "taupair-pair-aware-recode-heldout-20261007-v1"
CURVES = {
    "glv-j0-32": (4294967377, 15, 23729779, (481899190, 1998487369)),
    "j0-56": (2305843009213693951, 7, 53624256071278747,
               (1839617427631136375, 725584580046817702)),
}


def next_u64(state):
    state = (state + 0x9E3779B97F4A7C15) & MASK
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return state, z ^ (z >> 31)


def mix64(value):
    value &= MASK
    value ^= value >> 33
    value = value * 0xff51afd7ed558ccd & MASK
    value ^= value >> 33
    value = value * 0xc4ceb9fe1a85ec53 & MASK
    return value ^ (value >> 33)


def add(left, right, prime):
    if left is None:
        return right
    if right is None:
        return left
    x1, y1 = left
    x2, y2 = right
    if x1 == x2 and (y1 + y2) % prime == 0:
        return None
    if left == right:
        slope = 3 * x1 * x1 * pow(2 * y1, -1, prime) % prime
    else:
        slope = (y2 - y1) * pow((x2 - x1) % prime, -1, prime) % prime
    x3 = (slope * slope - x1 - x2) % prime
    return x3, (slope * (x1 - x3) - y1) % prime


def multiply(point, scalar, prime):
    result = None
    while scalar:
        if scalar & 1:
            result = add(result, point, prime)
        point = add(point, point, prime)
        scalar >>= 1
    return result


def main():
    manifest_path = HERE / "inputs.json"
    if manifest_path.exists():
        raise SystemExit("held-out manifest exists; refusing overwrite")
    prior = [json.loads((HERE.parent / name / "inputs.json").read_text())
             for name in ("prime-j0-joint-tau-stream", "prime-j0-hot-orbit-table",
                          "prime-j0-paired-lattice-stream", "prime-j0-unit-gauge-stream",
                          "prime-j0-gauge-trellis", "prime-j0-free-gauge",
                          "prime-j0-gauge-aware-five", "prime-j0-paired-tau",
                          "prime-j0-taupair-steer")]
    manifest = {"schema": 1, "label": LABEL, "count": COUNT,
                "oracle": "independent_affine_scalar_and_mix64_digest", "curves": {}}
    for curve, (prime, b, order, base) in CURVES.items():
        if (base[1] ** 2 - base[0] ** 3 - b) % prime:
            raise SystemExit(f"base is off curve: {curve}")
        if multiply(base, order, prime) is not None:
            raise SystemExit(f"base has wrong order: {curve}")
        partner = multiply(base, 37, prime)
        seed = int.from_bytes(hashlib.sha256(f"{LABEL}:{curve}".encode()).digest()[:8],
                              "little")
        pairs = [(0, 0), (1, 0), (0, 1), (1, 1),
                 (order - 1, order - 1), (order, 2 * order),
                 (MASK, MASK), (MASK, order - 1)]
        state = seed
        while len(pairs) < COUNT:
            state, a = next_u64(state)
            state, c = next_u64(state)
            pairs.append((a, c))
        raw = b"".join(struct.pack("<QQ", a, c) for a, c in pairs)
        digest = hashlib.sha256(raw).hexdigest()
        if digest in (entry["curves"][curve]["sha256"] for entry in prior):
            raise SystemExit(f"fixture reuses prior bytes: {curve}")
        input_digest = 0xf1d9ee7c70d6b80f
        output_digest = 0x513adf887a8b4d29
        for index, (a, c) in enumerate(pairs):
            input_digest = mix64(input_digest ^ mix64(a) ^ mix64((c + index) & MASK))
            point = multiply(base, (a + 37 * c) % order, prime)
            x, y, infinity = (0, 0, 1) if point is None else (*point, 0)
            output_digest = mix64(output_digest ^ mix64((x + index) & MASK) ^
                                  mix64(y) ^ infinity)
        name = f"heldout-{curve}.bin"
        path = HERE / name
        if path.exists():
            raise SystemExit(f"{name} exists; refusing overwrite")
        path.write_bytes(raw)
        manifest["curves"][curve] = {
            "file": name, "sha256": digest, "seed_hex": f"{seed:016x}",
            "subgroup_order": order, "base_x": base[0], "base_y": base[1],
            "partner_x": partner[0], "partner_y": partner[1],
            "generic_input_digest": f"{input_digest:016x}",
            "generic_output_digest": f"{output_digest:016x}",
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(manifest_path)


if __name__ == "__main__":
    main()
