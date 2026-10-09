#!/usr/bin/env python3
"""Freeze all four coset action streams in a cross-language byte encoding."""

import hashlib
import json
from pathlib import Path

from alternate_digit_atlas import digit_table
from atlas_portfolio import SEEDS
from coset_selector import FIXTURES
from make_zero_tau_action_fingerprints import fingerprint
from mixed_atlas_screen import make_options
from screen_coset_representatives import candidates
from screen_radix_policy import recode as radix_recode
from selective_mixed_atlas import recode as selective_recode


HERE = Path(__file__).resolve().parent


def main():
    tables = [digit_table(seeds) for seeds in SEEDS]
    options = make_options(tables, True)
    panels = []
    for path in FIXTURES:
        raw = path.read_bytes()
        rows = []
        for case in json.loads(raw)["cases"]:
            representatives = candidates(int(case["scalar_hex"], 16))[:3]
            assert representatives[0][2:4] == (
                int(case["short_a_hex"], 16), int(case["short_b_hex"], 16))
            digits, _ = selective_recode(representatives[0][2:4], tables, options)
            streams = [[("tau", (digit[0], digit[1]), digit[2])
                        if digit else ("tau", None, None) for digit in digits]]
            for _, _, a, b, _, _ in representatives:
                actions, status = radix_recode((a, b), tables[0], "skip_zero_tau")
                assert status == "verified" and actions is not None
                streams.append(actions)
            rows.append({"index": case["index"],
                         "lengths": [len(stream) for stream in streams],
                         "fnv64": [fingerprint(stream) for stream in streams]})
        panels.append({"fixture": path.name,
                       "fixture_sha256": hashlib.sha256(raw).hexdigest(),
                       "cases": len(rows), "rows": rows})
    result = {"schema": 1, "algorithm": "fnv1a64-action-byte-sequence-v1",
              "panels": panels,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cpu_speedup_claim": None}
    target = HERE / "coset-fingerprints.json"
    if target.exists():
        raise SystemExit("coset fingerprints exist; refusing overwrite")
    target.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"cases": sum(panel["cases"] for panel in panels),
                      "file_sha256": hashlib.sha256(target.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
