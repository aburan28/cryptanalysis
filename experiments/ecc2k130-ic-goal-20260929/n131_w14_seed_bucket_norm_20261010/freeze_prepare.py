#!/usr/bin/env python3
"""Freeze exact N131 W14 fixed-seed source-root construction."""

import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SUPPORT = BASE / "n131_w14_ten_source_gate_20261009/support_w14.tsv"
CONTROL = BASE / "n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "prepare_protocol.json"
    if output.exists():
        raise FileExistsError(output)
    ast.parse((HERE / "prepare.py").read_text())
    control = json.loads(CONTROL.read_text())["panels"]["131"]
    assert control["rotations"] == [26, 39] and control["seed_sum"] == 2
    assert control["group_replay"] is True and control["pair_equations"] is True
    data = {"status": "FROZEN", "proposal_id": "Q20261010045900",
            "candidate_id": None, "target_count": 0,
            "curve_id": control["curve_id"], "source_dimension": 14,
            "seed_sum": 2, "rotations": [26, 39],
            "wall_cap_seconds": 120, "rss_cap_bytes": 4294967296,
            "sha256": {"source": sha(HERE / "prepare.py"), "support": sha(SUPPORT),
                       "control": sha(CONTROL),
                       "runtime": sha(HERE / "sage_runtime_info.json")}}
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
