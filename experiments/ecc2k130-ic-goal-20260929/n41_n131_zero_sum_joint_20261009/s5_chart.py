#!/usr/bin/env python3
"""Derive a pinned correctness formula from the frozen S5 control and exact row."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    formula = HERE / "s5_chart.xcnf"
    receipt_path = HERE / "s5_chart_build.json"
    if formula.exists() or receipt_path.exists():
        raise FileExistsError("preserve prior S5 chart formula")
    chart = json.loads((HERE / "witness_chart.json").read_text())
    build = json.loads((HERE / "s5_control_build.json").read_text())
    assert chart["status"] == "PASS_EXACT_ALGEBRAIC_CHART"
    assert build["sha256"]["formula"] == sha(HERE / "s5_control.xcnf")
    assignments = [(wire, bool((value >> i) & 1))
                   for wires, value in zip(build["block_output_wire_rows"],
                                           chart["block_u"])
                   for i, wire in enumerate(wires)]
    assignments.extend((wire, i == chart["target_fiber_index"])
                       for i, wire in enumerate(build["target_flag_wires"]))
    assert len(assignments) == 4*41 + 4
    assert len({wire for wire, _ in assignments}) == len(assignments)
    lines = (HERE / "s5_control.xcnf").read_text().splitlines()
    header = lines[0].split()
    assert header[:2] == ["p", "cnf"]
    header[3] = str(int(header[3]) + len(assignments))
    with formula.open("w") as handle:
        handle.write(" ".join(header) + "\n")
        handle.write("\n".join(lines[1:]) + "\n")
        handle.writelines(f"{wire if bit else -wire} 0\n"
                          for wire, bit in assignments)
    receipt = {"status": "BUILT_PINNED_CHART",
               "proposal_id": "Q20261009205500", "candidate_id": None,
               "pinned_field_bits": len(assignments),
               "formula_variables": int(header[2]),
               "sha256": {"source": sha(__file__),
                          "control_formula": sha(HERE / "s5_control.xcnf"),
                          "control_build": sha(HERE / "s5_control_build.json"),
                          "witness_chart": sha(HERE / "witness_chart.json"),
                          "formula": sha(formula)}}
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "pinned_field_bits": len(assignments),
                      "formula_sha256": sha(formula)}, sort_keys=True))


if __name__ == "__main__":
    main()
