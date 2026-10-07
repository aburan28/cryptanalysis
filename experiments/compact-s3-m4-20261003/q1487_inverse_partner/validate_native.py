#!/usr/bin/env python3
"""Replay Q1487 inverse-partner support against direct N53/N83 S3 scans."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
BINARY = HERE / "native_selftest"
OUT = HERE / "native_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    compile_receipt = HERE / "compile_receipt.json"
    build = json.loads(compile_receipt.read_text())
    assert build["proposal_id"] == "Q1487"
    assert build["selftest_binary_sha256"] == sha(BINARY)
    rows = []
    for n in (53, 83):
        input_dir = PARENT / "q1482_window_s3" / "inputs" / f"n{n}_ordinary"
        field = PARENT / "q1420_root_theory" / f"n{n}_field.txt"
        window = PARENT / "q1486_window_aware_pair" / "inputs" / (
            f"n{n}_ordinary") / "windows.map"
        command = [str(BINARY), str(field), str(input_dir / "variables.txt"),
                   str(input_dir / "targets.txt"), str(window)]
        completed = subprocess.run(command, check=True, capture_output=True,
                                   text=True, timeout=180)
        assert not completed.stderr
        result = json.loads(completed.stdout)
        assert result["status"] == "passed" and result["degree_n"] == n
        assert result["large_partner_cases"] > 0
        assert result["direct_s3_evaluations"] > result[
            "inverse_root_calls"] > 0
        rows.append({
            "degree_n": n,
            "curve_id": ("EC1N53Ckb1hf77aab617904" if n == 53 else
                         "EC1N83Ckb1h876c2921cb64"),
            "result": result,
            "stdout": completed.stdout.strip(),
            "field_sha256": sha(field),
            "variable_map_sha256": sha(input_dir / "variables.txt"),
            "targets_sha256": sha(input_dir / "targets.txt"),
            "window_map_sha256": sha(window),
        })
    return {
        "kind": "q1487_native_inverse_s3_direct_scan_validation",
        "proposal_id": "Q1487",
        "status": "passed",
        "rows": rows,
        "selftest_binary_sha256": sha(BINARY),
        "compile_receipt_sha256": sha(compile_receipt),
        "source_sha256": sha(Path(__file__)),
        "runtime_info_sha256": sha(HERE / "sage_runtime_info.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        assert json.loads(OUT.read_text()) == result
    else:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"proposal_id": "Q1487", "status": result["status"],
                      "cases": [r["degree_n"] for r in result["rows"]]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
