#!/usr/bin/env python3
"""Replay a native-XOR satisfiable formula through all four selector masks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q1460 = HERE.parent / "q20261011_wdsat_shared_prefix"
sys.path.insert(0, str(Q1460))
from prepare import evaluate  # noqa: E402
from phase_schedule import INDICES, phases  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    input_path = HERE / "smoke.xcnf"
    output_path = HERE / "smoke_receipt.json"
    assert not input_path.exists() and not output_path.exists()
    source = b"p cnf 2141 2\n1 0\nx1 2 0\n"
    input_path.write_bytes(source)
    build = json.loads((HERE / "build_receipt.json").read_text())
    binary = Path(build["binary_path"])
    assert sha(binary.read_bytes()) == build["binary_sha256"]
    rows = []
    for phase in INDICES:
        env = os.environ.copy()
        env["Q1469_ORDER_MODE"] = "selector_pair_mids"
        env["Q1472_PHASE_INDEX"] = "0"
        env["Q1473_SELECTOR_PHASE"] = str(phase)
        process = subprocess.run([str(binary), "-i", str(input_path)], env=env,
                                 capture_output=True, timeout=60)
        assert process.returncode == 0
        stderr = process.stderr.decode()
        assert stderr.splitlines().count("Q1472_PHASE 0 0") == 1
        assert stderr.splitlines().count(
            f"Q1473_SELECTOR_PHASE {phase} 2140 2141") == 1
        models = [line.strip() for line in process.stdout.decode().splitlines()
                  if len(line.strip()) == 2141 and
                  set(line.strip()) <= {"0", "1"}]
        assert len(models) == 1
        model = {i + 1: bit == "1" for i, bit in enumerate(models[0])}
        replay = evaluate(source, model)
        checkpoints = [int(x) for x in re.findall(r"^Q1464_BRANCH (\d+)$",
                                                    stderr, re.MULTILINE)]
        work = [list(map(int, x)) for x in re.findall(
            r"^Q1473_WORK (\d+) (\d+) (\d+)$", stderr, re.MULTILINE)]
        assert [x[0] for x in work] == checkpoints
        assert checkpoints == [1 << i for i in range(len(checkpoints))]
        final = [list(map(int, x)) for x in re.findall(
            r"^Q1473_WORK_FINAL (\d+) (\d+)$", stderr, re.MULTILINE)]
        assert len(final) == 1 and all(x > 0 for x in final[0])
        assert all(final[0][index] >= work[-1][index + 1]
                   for index in range(2))
        rows.append({"phase": phase, "flip_ids": phases()[phase]["flip_ids"],
                     "status": "SAT_REPLAYED_XCNF", "replay": replay,
                     "branch_checkpoints": checkpoints,
                     "work_checkpoints": work,
                     "cnf_set_true_calls": final[0][0],
                     "xor_set_true_calls": final[0][1],
                     "stdout_sha256": sha(process.stdout),
                     "stderr_sha256": sha(process.stderr)})
    output = {"proposal_id": "Q1473", "status": "PASS",
              "input_sha256": sha(source),
              "binary_sha256": build["binary_sha256"],
              "build_receipt_sha256": sha((HERE / "build_receipt.json").read_bytes()),
              "source_sha256": sha(Path(__file__).read_bytes()),
              "rows": rows}
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("Q1473 smoke PASS", len(rows), "selector masks")


if __name__ == "__main__":
    main()
