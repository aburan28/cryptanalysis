#!/usr/bin/env python3
"""Verify the intact chart model after receipt serialization failed."""

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "n41_n131_zero_sum_joint_20261009"))
from run import model_bits, verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = HERE / "chart" / "recovered_result.json"
    if output.exists():
        raise FileExistsError(output)
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert protocol["status"] == "FROZEN_FORWARD"
    for key, relative in protocol["files"].items():
        assert protocol["sha256"][key] == sha(HERE / relative), key
    chart = json.loads((HERE / "forward_chart.json").read_text())
    build = json.loads((HERE / "control_build.json").read_text())
    stdout_file = HERE / "chart" / "stdout.txt"
    model_file = HERE / "chart" / "model_bits.txt"
    text = stdout_file.read_text()
    assert "s SATISFIABLE" in text.splitlines()
    bits = model_bits(text, build["formula_variables"])
    assert model_file.read_text().strip() == bits
    valid, checked = verify_formula(HERE / "chart.xcnf", bits)
    assert valid

    def unpack(wires):
        return sum((bits[wire-1] == "1") << i for i, wire in enumerate(wires))

    masks = [[unpack(a), unpack(b), unpack(a)^unpack(b)]
             for a, b in build["mask_wire_rows"]]
    pairs = [unpack(row) for row in build["pair_output_wire_rows"]]
    blocks = [unpack(row) for row in build["block_output_wire_rows"]]
    branches = [[int(bits[wire-1] == "1") for wire in row]
                for row in build["root_branch_wires"]]
    flags = [bits[wire-1] == "1" for wire in build["target_flag_wires"]]
    assert masks == chart["source_masks"]
    assert pairs == chart["pair_u"]
    assert blocks == chart["block_u"]
    assert branches == chart["root_branch_bits"]
    assert sum(flags) == 1 and flags.index(True) == chart["target_fiber_index"]
    receipt = {
        "status": "RECOVERED_CHART_MODEL", "candidate_id": None,
        "proposal_id": chart["proposal_id"],
        "producer_failure": "KeyError mask_wire_rows in chart receipt formatting after formula assignment verification",
        "formula_assignment_check": checked,
        "model_masks": masks, "model_pair_u": pairs,
        "model_block_u": blocks, "model_root_branch_bits": branches,
        "model_target_fiber_index": flags.index(True),
        "solver_wall_ns": None,
        "sha256": {"source": sha(Path(__file__)),
                   "protocol": sha(HERE / "protocol.json"),
                   "forward_chart": sha(HERE / "forward_chart.json"),
                   "formula": sha(HERE / "chart.xcnf"),
                   "stdout": sha(stdout_file), "model_bits": sha(model_file)},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "formula_assignment_check": checked,
                      "model_masks": masks}, sort_keys=True))


if __name__ == "__main__":
    main()
