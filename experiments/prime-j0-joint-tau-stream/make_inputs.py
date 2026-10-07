#!/usr/bin/env python3
"""Create the prospective, fixed public double-scalar panel.

The binary format is 1024 consecutive (a, b) pairs, each as two uint64 LE.
The seed is derived from the curve name and a fresh experiment label. No
results from either τ arm enter this generator.
"""
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
COUNT = 1024
MASK = (1 << 64) - 1
CURVES = {
    "glv-j0-32": 23729779,
    "j0-56": 53624256071278747,
}
LABEL = "joint-prime-j0-tau-stream-prospective-20261007-v1"


def splitmix64(state):
    state = (state + 0x9E3779B97F4A7C15) & MASK
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return state, z ^ (z >> 31)


def make_pairs(curve, order):
    seed = int.from_bytes(hashlib.sha256(f"{LABEL}:{curve}".encode()).digest()[:8], "little")
    pairs = [
        (0, 0), (1, 0), (0, 1), (1, 1),
        (order - 1, order - 1), (order, 2 * order),
        (MASK, MASK), (MASK, order - 1),
    ]
    state = seed
    while len(pairs) < COUNT:
        state, a = splitmix64(state)
        state, b = splitmix64(state)
        pairs.append((a, b))
    return seed, pairs


def main():
    manifest = {"schema": 1, "label": LABEL, "count": COUNT, "curves": {}}
    manifest_path = HERE / "inputs.json"
    if manifest_path.exists():
        raise SystemExit("inputs.json already exists; refusing to overwrite the frozen panel")
    for curve, order in CURVES.items():
        seed, pairs = make_pairs(curve, order)
        raw = b"".join(struct.pack("<QQ", a, b) for a, b in pairs)
        path = HERE / f"{curve}.bin"
        if path.exists():
            raise SystemExit(f"{path.name} already exists; refusing to overwrite")
        path.write_bytes(raw)
        manifest["curves"][curve] = {
            "file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "seed_hex": f"{seed:016x}",
            "subgroup_order": order,
            "generic_input_digest": None,
            "generic_output_digest": None,
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(manifest_path)


if __name__ == "__main__":
    main()
