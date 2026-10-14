#!/usr/bin/env python3
"""Account ordinary-path 64-bit products for the frozen axis-152 replay."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPLAY = HERE / "replay.json"
OUTPUT = HERE / "model.json"
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs"
MONTGOMERY = ROOT / "suite/src/ct_bignum.rs"

# Source loops: 16 products for the schoolbook wide product, 4 for m,
# and 16 in the Montgomery reduction. The ordinary XYZZ addition has
# eight general products and two squares, all using the same routine.
MONT_FIELD = 36
FIELD_OPS_PER_ADD = 10
# Canonical Karatsuba Solinas: nine variable products and seven folds.
SOLINAS_KARATSUBA_FIELD = 16
# The reference unit rotation uses the 16-product schoolbook wide
# multiply and seven Solinas folds; the candidate uses Karatsuba.
MONT_ROTATION = 23
SOLINAS_ROTATION = 16


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def make() -> dict:
    replay = json.loads(REPLAY.read_text())
    panels = []
    for panel in replay["panels"]:
        additions = panel["total_additions"]
        rotations = panel["total_rotations"]
        reference = MONT_FIELD * FIELD_OPS_PER_ADD * additions + MONT_ROTATION * rotations
        candidate = (SOLINAS_KARATSUBA_FIELD * FIELD_OPS_PER_ADD * additions
                     + SOLINAS_ROTATION * rotations)
        saved = reference - candidate
        assert saved == 200 * additions + 7 * rotations
        panels.append({
            "fixture": panel["fixture"], "additions": additions,
            "rotations": rotations,
            "reference_64bit_products": reference,
            "candidate_64bit_products": candidate,
            "saved_64bit_products": saved,
            "saved_fraction_decimal": f"{saved / reference:.9f}",
        })
    return {
        "schema": 1,
        "status": "ordinary_nonexceptional_source_product_model",
        "field_ops_per_addition": FIELD_OPS_PER_ADD,
        "reference_64bit_products_per_field_op": MONT_FIELD,
        "candidate_64bit_products_per_field_op": SOLINAS_KARATSUBA_FIELD,
        "reference_64bit_products_per_rotation": MONT_ROTATION,
        "candidate_64bit_products_per_rotation": SOLINAS_ROTATION,
        "panels": panels,
        "replay_sha256": digest(REPLAY),
        "native_source_sha256": digest(NATIVE),
        "montgomery_source_sha256": digest(MONTGOMERY),
        "model_source_sha256": digest(Path(__file__)),
    }


def main() -> None:
    payload = (json.dumps(make(), indent=2, sort_keys=True) + "\n").encode()
    if "--check" in sys.argv:
        assert OUTPUT.read_bytes() == payload
    else:
        if OUTPUT.exists():
            raise SystemExit("model exists; use --check")
        OUTPUT.write_bytes(payload)
    print(json.dumps(make()["panels"], sort_keys=True))


if __name__ == "__main__":
    main()
