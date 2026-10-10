#!/usr/bin/env python3
"""Pin the independently replayed forward witness in the fixed-mask formula."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "chart.xcnf"
    receipt_path = HERE / "chart_build.json"
    if output.exists() or receipt_path.exists():
        raise FileExistsError("preserve prior chart formula")
    chart = json.loads((HERE / "forward_chart.json").read_text())
    build = json.loads((HERE / "control_build.json").read_text())
    control = HERE / "control.xcnf"
    assert chart["status"] == "PASS_FORWARD_ROOT_CHART"
    assert build["sha256"]["formula"] == sha(control)
    assert chart["source_masks"] == build["control_masks"]
    assignments = []
    for key, values in (("pair_output_wire_rows", chart["pair_u"]),
                        ("block_output_wire_rows", chart["block_u"])):
        assignments.extend((wire, bool(value >> i & 1))
                           for row, value in zip(build[key], values)
                           for i, wire in enumerate(row))
    assignments.extend((wire, bool(bit))
                       for rows, bits in zip(build["root_branch_wires"],
                                             chart["root_branch_bits"])
                       for wire, bit in zip(rows, bits))
    assignments.extend((wire, i == chart["target_fiber_index"])
                       for i, wire in enumerate(build["target_flag_wires"]))
    assert len(assignments) == 340
    assert len(set(wire for wire, _ in assignments)) == len(assignments)
    with control.open() as source, output.open("w") as destination:
        header = source.readline().split()
        assert header[:2] == ["p", "cnf"]
        header[3] = str(int(header[3]) + len(assignments))
        destination.write(" ".join(header) + "\n")
        for line in source:
            destination.write(line)
        for wire, bit in assignments:
            destination.write(f"{wire if bit else -wire} 0\n")
    receipt = {"status": "BUILT_PINNED_CHART", "proposal_id": chart["proposal_id"],
               "candidate_id": None, "pinned_bits": len(assignments),
               "formula_variables": build["formula_variables"],
               "sha256": {"source": sha(Path(__file__)),
                          "control_formula": sha(control),
                          "control_build": sha(HERE / "control_build.json"),
                          "forward_chart": sha(HERE / "forward_chart.json"),
                          "formula": sha(output)}}
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "pinned_bits": len(assignments),
                      "formula_sha256": receipt["sha256"]["formula"]}, sort_keys=True))


if __name__ == "__main__":
    main()
