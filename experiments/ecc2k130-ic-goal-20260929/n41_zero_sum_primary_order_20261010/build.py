#!/usr/bin/env python3
"""Reindex exact N41 formulas with root bits and source masks first."""

import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "n41_n131_zero_sum_forward_20261009"
JOINT = HERE.parent / "n41_n131_zero_sum_joint_20261009"
sys.path.insert(0, str(JOINT))
from run import verify_formula


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    outputs = [HERE / name for name in
               ("ordered_control.xcnf", "ordered_public.xcnf",
                "known_model_bits.txt", "build.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("preserve previous ordered formula build")
    source_protocol = json.loads((SOURCE / "protocol.json").read_text())
    assert source_protocol["status"] == "FROZEN_FORWARD"
    for key, relative in source_protocol["files"].items():
        assert source_protocol["sha256"][key] == sha(SOURCE / relative), key
    source_build = json.loads((SOURCE / "public_build.json").read_text())
    control_build = json.loads((SOURCE / "control_build.json").read_text())
    assert source_build["root_branch_wires"] == control_build["root_branch_wires"]
    assert source_build["mask_wire_rows"] == control_build["mask_wire_rows"]
    assert source_build["target_flag_wires"] == control_build["target_flag_wires"]
    n = source_build["formula_variables"]
    roots = [wire for pair in source_build["root_branch_wires"] for wire in pair]
    masks = [wire for a, b in source_build["mask_wire_rows"]
             for row in (a, b) for wire in row]
    flags = source_build["target_flag_wires"]
    primary = roots + masks + flags
    assert len(roots) == 8 and len(masks) == 56 and len(flags) == 4
    assert len(set(primary)) == len(primary) == 68
    assert all(0 < wire <= n for wire in primary)
    selected = set(primary)
    new_to_old = [0] + primary + [wire for wire in range(1, n + 1)
                                    if wire not in selected]
    assert len(new_to_old) == n + 1
    old_to_new = [0] * (n + 1)
    for new, old in enumerate(new_to_old[1:], 1):
        old_to_new[old] = new
    assert sorted(old_to_new[1:]) == list(range(1, n + 1))

    def mapped(token):
        old = int(token)
        return str(old_to_new[abs(old)] * (1 if old > 0 else -1))

    timings = {}
    for mode in ("control", "public"):
        source = SOURCE / f"{mode}.xcnf"
        output = HERE / f"ordered_{mode}.xcnf"
        assert sha(source) == json.loads((SOURCE / f"{mode}_build.json").read_text())["sha256"]["formula"]
        started = time.monotonic_ns()
        counts = {"clauses": 0, "xors": 0}
        with source.open() as input_handle, output.open("w") as output_handle:
            header = input_handle.readline()
            assert header.split()[:3] == ["p", "cnf", str(n)]
            output_handle.write(header)
            for line in input_handle:
                words = line.split()
                if not words or words[0] == "c":
                    output_handle.write(line)
                    continue
                assert words[-1] == "0"
                if words[0] == "x":
                    output_handle.write("x " + " ".join(map(mapped, words[1:-1])) + " 0\n")
                    counts["xors"] += 1
                else:
                    output_handle.write(" ".join(map(mapped, words[:-1])) + " 0\n")
                    counts["clauses"] += 1
        build = json.loads((SOURCE / f"{mode}_build.json").read_text())
        assert counts == {"clauses": build["cnf_clauses"],
                          "xors": build["native_xor_rows"]}
        timings[mode] = {"mapping_ns": time.monotonic_ns() - started,
                         "counts": counts, "bytes": output.stat().st_size}

    old_bits = (SOURCE / "chart/model_bits.txt").read_text().strip()
    assert len(old_bits) == n
    assert verify_formula(SOURCE / "control.xcnf", old_bits)[0]
    assert verify_formula(SOURCE / "public.xcnf", old_bits)[0]
    new_bits = "".join(old_bits[old-1] for old in new_to_old[1:])
    (HERE / "known_model_bits.txt").write_text(new_bits + "\n")
    assert verify_formula(HERE / "ordered_control.xcnf", new_bits)[0]
    assert verify_formula(HERE / "ordered_public.xcnf", new_bits)[0]
    receipt = {
        "status": "BUILT_EXACT_REINDEX", "proposal_id": "Q20261010222000",
        "candidate_id": None, "formula_variables": n,
        "primary_variable_count": len(primary),
        "primary_old_wires": primary,
        "primary_order": "eight forward root bits, 56 source mask bits, four target-fiber flags, then all remaining wires in original order",
        "full_permutation_rule": "new_to_old=[0]+primary+[i for i in 1..n if i not in primary]",
        "build": timings,
        "positive_assignment_check": "both original and both reindexed formulas satisfy full chart model",
        "sha256": {"source": sha(Path(__file__)),
                   "source_protocol": sha(SOURCE / "protocol.json"),
                   "source_control_formula": sha(SOURCE / "control.xcnf"),
                   "source_public_formula": sha(SOURCE / "public.xcnf"),
                   "source_control_build": sha(SOURCE / "control_build.json"),
                   "source_public_build": sha(SOURCE / "public_build.json"),
                   "source_chart_model": sha(SOURCE / "chart/model_bits.txt"),
                   "ordered_control_formula": sha(HERE / "ordered_control.xcnf"),
                   "ordered_public_formula": sha(HERE / "ordered_public.xcnf"),
                   "known_model_bits": sha(HERE / "known_model_bits.txt")},
    }
    (HERE / "build.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "primary": len(primary),
                      "counts": timings["control"]["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
