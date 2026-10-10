#!/usr/bin/env python3
"""Freeze public N41 diagonal-atom 4+4 input and source digests."""

import hashlib
import json
import platform
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREEN = HERE / "screen.json"
JOIN = HERE / "join.cpp"
INCLUDED = HERE / "../../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = json.loads(SCREEN.read_text())
    assert data["actual_usable_points_B"] == 512
    assert data["signed_frobenius_columns_K"] == 26
    assert len(data["slots"]) == 8
    target = data["public_target"]
    lines = [f"{target[0]} {target[1]} {data['subgroup_order']} 8"]
    for slot in data["slots"]:
        assert len(slot) == 64
        lines.append("64")
        for row in slot:
            x, y = row["point"]
            lines.append(f"{x} {y} {row['source_column']} {row['mask']} 0 {row['sign']}")
    input_path = HERE / "input.txt"
    if input_path.exists():
        assert input_path.read_text() == "\n".join(lines) + "\n"
    else:
        input_path.write_text("\n".join(lines) + "\n")
    protocol = {
        "status": "FROZEN", "candidate_id": None,
        "purpose": "public-only indexed relation support for eight diagonal atoms",
        "curve_id": data["curve_id"], "public_target": target,
        "source_sha256": {"screen": sha(SCREEN), "join": sha(JOIN),
                          "included_arithmetic": sha(INCLUDED),
                          "input": sha(input_path), "prepare": sha(Path(__file__))},
        "compile": ["clang++", "-std=c++17", "-O3", "-Wall", "-Wextra", "join.cpp", "-o", "join"],
        "run": ["./join", "input.txt", "join_result.json"],
        "limits": {"workers": 1, "setup_wall_seconds": 120,
                   "online_wall_seconds": 120, "peak_rss_bytes": 4294967296},
        "host": {"machine": platform.machine(), "system": platform.system(),
                  "release": platform.release()},
        "accounting": "indexed setup reusable; online clock starts at public-target lookup"
    }
    path = HERE / "protocol.json"
    if path.exists():
        assert json.loads(path.read_text()) == protocol
    else:
        path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": protocol["status"], "input_sha256": sha(input_path),
                      "join_sha256": sha(JOIN), "rows": len(lines) - 9}, indent=2))


if __name__ == "__main__":
    main()
