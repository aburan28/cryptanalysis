#!/usr/bin/env python3
"""Write the frozen N41 public point and four exact source windows for native query."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads((HERE / "query_protocol.json").read_text())
    if sha(Path(__file__)) != frozen["source_sha256"]["make_input.py"]:
        raise ValueError("input builder changed after freeze")
    for name, expected in frozen["input_sha256"].items():
        if sha(HERE / name) != expected:
            raise ValueError(f"query input changed: {name}")
    protocol = json.loads((HERE / "protocol.json").read_text())
    for name, expected in protocol["input_sha256"].items():
        if sha(Path(protocol["inputs"][name])) != expected:
            raise ValueError(f"source geometry changed: {name}")
    output = HERE / "public_input.txt"
    if output.exists():
        raise FileExistsError("preserve first frozen public input")
    geometry = json.loads(Path(protocol["inputs"]["geometry"]).read_text())["n41"]
    if geometry["curve_id"] != protocol["curve_id"]:
        raise ValueError("curve ID changed")
    qx, qy = protocol["public_target_q"]
    lines = [f"{qx} {qy} {protocol['subgroup_order']} 4"]
    for rotation in frozen["pair_rotations"]:
        rows = geometry["point_rows_by_unique_rotation"][str(rotation)]
        if len(rows) != 64:
            raise ValueError("source window size changed")
        lines.append("64")
        for x, y, column, mask in rows:
            lines.append(f"{x} {y} {column} {mask}")
    output.write_text("\n".join(lines) + "\n")
    receipt = {"status": "FROZEN_PUBLIC_INPUT_WRITTEN",
               "public_input_sha256": sha(output), "source_sha256": sha(Path(__file__)),
               "query_protocol_sha256": sha(HERE / "query_protocol.json"),
               "source_points": 256, "pair_rotations": frozen["pair_rotations"]}
    (HERE / "public_input_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "public_input_sha256": receipt["public_input_sha256"]}))


if __name__ == "__main__":
    main()
