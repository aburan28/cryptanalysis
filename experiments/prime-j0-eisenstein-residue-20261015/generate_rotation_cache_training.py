#!/usr/bin/env python3
"""Generate an independent scalar-only training stream for cache selection."""

from hashlib import sha256, shake_256
from pathlib import Path
import json

ORDER = int("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141", 16)
DOMAIN = b"prime-j0-rotation-cache-training-v1"
COUNT = 20000


def main(output: Path) -> None:
    seen = set()
    cases = []
    counter = 0
    while len(cases) < COUNT:
        digest = shake_256(DOMAIN + counter.to_bytes(8, "big")).digest(32)
        scalar = int.from_bytes(digest, "big")
        counter += 1
        if scalar == 0 or scalar >= ORDER or scalar in seen:
            continue
        seen.add(scalar)
        cases.append({"scalar_hex": f"{scalar:064x}"})
    data = {"schema": 1, "domain_hex": DOMAIN.hex(), "count": COUNT,
            "counters_consumed": counter, "cases": cases}
    output.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
    print("training_sha256=" + sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main(Path(__file__).resolve().parent / "rotation-cache-training-20000.json")
