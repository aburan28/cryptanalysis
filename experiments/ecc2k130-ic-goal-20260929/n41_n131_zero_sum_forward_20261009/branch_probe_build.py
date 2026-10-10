#!/usr/bin/env python3
"""Derive a branch-only propagation control from the frozen mask control."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    formula = HERE / "branch_probe.xcnf"
    receipt_file = HERE / "branch_probe_build.json"
    if formula.exists() or receipt_file.exists():
        raise FileExistsError("preserve prior branch probe")
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_FORWARD"
    chart = json.loads((HERE / "forward_chart.json").read_text())
    build = json.loads((HERE / "control_build.json").read_text())
    control = HERE / "control.xcnf"
    assert build["sha256"]["formula"] == sha(control)
    assert chart["source_masks"] == build["control_masks"]
    assignments = [(wire, bool(bit))
                   for wires, bits in zip(build["root_branch_wires"],
                                          chart["root_branch_bits"])
                   for wire, bit in zip(wires, bits)]
    assert len(assignments) == 8
    with control.open() as source, formula.open("w") as destination:
        header = source.readline().split()
        assert header[:2] == ["p", "cnf"]
        header[3] = str(int(header[3]) + len(assignments))
        destination.write(" ".join(header) + "\n")
        for line in source:
            destination.write(line)
        for wire, bit in assignments:
            destination.write(f"{wire if bit else -wire} 0\n")
    receipt = {"status": "BUILT_BRANCH_PROBE", "candidate_id": None,
               "proposal_id": chart["proposal_id"],
               "pins": "eight root bits from independently replayed relation; source masks already fixed; pair and block outputs plus target flag remain free",
               "formula_variables": build["formula_variables"],
               "pinned_root_bits": len(assignments),
               "sha256": {"source": sha(Path(__file__)),
                          "runner": sha(HERE / "branch_probe_run.py"),
                          "parent_protocol": sha(HERE / "protocol.json"),
                          "control_formula": sha(control),
                          "control_build": sha(HERE / "control_build.json"),
                          "chart": sha(HERE / "forward_chart.json"),
                          "formula": sha(formula)}}
    receipt_file.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "pinned_root_bits": 8,
                      "formula_sha256": sha(formula)}, sort_keys=True))


if __name__ == "__main__":
    main()
