#!/usr/bin/env python3
"""Freeze archived ordinary states and positive Q1448 pair controls."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1446 = PARENT / "q1446_joint_pair_span"
Q1448 = PARENT / "q1448_torsion_phi5"


def planted_line(n: int, control: dict) -> str:
    a, b = map(int, control["raw_leaf_x"][:2])
    weight = 4 if n == 53 else 6
    only_a, only_b = a & ~b, b & ~a
    assert only_a and only_b
    a_bit = (only_a & -only_a).bit_length() - 1
    b_bit = (only_b & -only_b).bit_length() - 1
    zeros = [bit for bit in range(n) if not ((a | b) >> bit & 1)]
    assert len(zeros) >= 18
    free = (1 << a_bit) | (1 << b_bit)
    free |= sum(1 << bit for bit in zeros[:18])
    fixed = ((1 << n) - 1) ^ free
    assert (a & fixed).bit_count() == weight - 2
    assert (b & fixed).bit_count() == weight - 2
    field = PARENT / "q1420_root_theory" / f"n{n}_field.txt"
    completed = subprocess.run(
        [str(HERE / "control_roots"), str(field), f"{a:x}", f"{b:x}"],
        check=True, capture_output=True, text=True)
    roots = completed.stdout.splitlines()
    assert roots and int(roots[0], 16)
    return " ".join(map(str, (
        f"n{n}_planted", 0, 0, roots[0], f"{fixed:x}", f"{a & fixed:x}",
        f"{fixed:x}", f"{b & fixed:x}")))


def ordinary_lines(n: int) -> list[str]:
    receipt = json.loads((Q1446 / f"runs/n{n}_ordinary/receipt.json").read_text())
    assert receipt["degree_n"] == n and receipt["proposal_id"] == "Q1446"
    rows = []
    for index, state in enumerate(receipt["solver_report"]["screen_snapshots"]):
        rows.append(" ".join(map(str, (
            f"n{n}_ordinary", index, state["pair"], state["mid_onb_hex"],
            state["a_fixed_mask_onb_hex"], state["a_ones_onb_hex"],
            state["b_fixed_mask_onb_hex"], state["b_ones_onb_hex"]))))
    assert len(rows) == 16
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    controls = json.loads((Q1448 / "validation.json").read_text())
    assert controls["status"] == "pass"
    by_degree = {row["degree_n"]: row for row in controls["rows"]}
    assert set(by_degree) == {53, 83}
    for n in (53, 83):
        lines = [planted_line(n, by_degree[n]), *ordinary_lines(n)]
        output = HERE / f"n{n}_inputs.txt"
        content = "\n".join(lines) + "\n"
        if args.check:
            assert output.read_text() == content
        else:
            if output.exists():
                raise FileExistsError(output)
            output.write_text(content)
    print("Q1461 frozen inputs: PASS" if args.check else
          "Q1461 positive controls and ordinary snapshots prepared")


if __name__ == "__main__":
    main()
