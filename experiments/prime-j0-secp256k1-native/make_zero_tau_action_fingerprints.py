#!/usr/bin/env python3
"""Compact cross-language fingerprints of zero-tau-rule actions."""

import hashlib
import json
from pathlib import Path
import struct

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from screen_radix_policy import recode
from zero_tau_rule import FIXTURES, POLICY


HERE = Path(__file__).resolve().parent
OFFSET = 0xCBF29CE484222325
PRIME = 0x100000001B3
MASK = (1 << 64) - 1


def fingerprint(actions):
    value = OFFSET
    for radix, digit, seed in actions:
        encoded = bytearray((1 if radix == "tau" else 2,
                             0 if digit is None else 1))
        if digit is not None:
            encoded.extend(struct.pack("<q", digit[0]))
            encoded.extend(struct.pack("<q", digit[1]))
            encoded.append(seed)
        for byte in encoded:
            value = ((value ^ byte) * PRIME) & MASK
    return f"{value:016x}"


def main():
    table = digit_table(SEEDS[0])
    panels = []
    for path in FIXTURES:
        raw = path.read_bytes()
        cases = json.loads(raw)["cases"]
        rows = []
        for case in cases:
            short = int(case["short_a_hex"], 16), int(case["short_b_hex"], 16)
            actions, status = recode(short, table, POLICY)
            assert status == "verified" and actions is not None
            rows.append({"index": case["index"],
                         "actions": len(actions),
                         "fnv64": fingerprint(actions)})
        panels.append({"fixture": path.name,
                       "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                       "cases": len(rows), "rows": rows})
    result = {"schema": 1, "algorithm": "fnv1a64-action-byte-sequence-v1",
              "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "recoder_sha256": hashlib.sha256((HERE / "zero_tau_rule.py").read_bytes()).hexdigest(),
              "cpu_speedup_claim": None}
    target = HERE / "zero-tau-action-fingerprints.json"
    if target.exists():
        raise SystemExit("action fingerprints exist; refusing overwrite")
    target.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"cases": sum(panel["cases"] for panel in panels),
                      "file_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
