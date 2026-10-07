#!/usr/bin/env python3
"""Fresh held-out scalar pairs for paired lattice representative selection."""
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASK = (1 << 64) - 1
COUNT = 1024
LABEL = "paired-lattice-heldout-20261007-v1"
CURVES = {"glv-j0-32": 23729779, "j0-56": 53624256071278747}


def next_u64(state):
    state = (state + 0x9E3779B97F4A7C15) & MASK
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return state, z ^ (z >> 31)


def main():
    manifest_path = HERE / "inputs.json"
    if manifest_path.exists():
        raise SystemExit("held-out manifest already exists; refusing overwrite")
    manifest = {"schema": 1, "label": LABEL, "count": COUNT, "curves": {}}
    old = json.loads((HERE.parent / "prime-j0-joint-tau-stream/inputs.json").read_text())
    hot = json.loads((HERE.parent / "prime-j0-hot-orbit-table/inputs.json").read_text())
    for curve, order in CURVES.items():
        seed = int.from_bytes(hashlib.sha256(f"{LABEL}:{curve}".encode()).digest()[:8], "little")
        pairs = [(0, 0), (1, 0), (0, 1), (1, 1),
                 (order - 1, order - 1), (order, 2 * order),
                 (MASK, MASK), (MASK, order - 1)]
        state = seed
        while len(pairs) < COUNT:
            state, a = next_u64(state)
            state, b = next_u64(state)
            pairs.append((a, b))
        raw = b"".join(struct.pack("<QQ", a, b) for a, b in pairs)
        digest = hashlib.sha256(raw).hexdigest()
        if digest in (old["curves"][curve]["sha256"], hot["curves"][curve]["sha256"]):
            raise SystemExit(f"held-out fixture reuses old bytes: {curve}")
        name = f"heldout-{curve}.bin"
        path = HERE / name
        if path.exists():
            raise SystemExit(f"{name} already exists; refusing overwrite")
        path.write_bytes(raw)
        manifest["curves"][curve] = {
            "file": name, "sha256": digest,
            "seed_hex": f"{seed:016x}", "subgroup_order": order,
            "generic_input_digest": None, "generic_output_digest": None,
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(manifest_path)


if __name__ == "__main__":
    main()
