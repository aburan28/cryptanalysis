#!/usr/bin/env python3
"""Require independent Sage replay to reject corrupted archived controls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAGE = "/Volumes/SSD990/cryptanalysis/sage"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--runtime-info", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    original = json.loads(args.result.read_text())
    report = {"status": "PASS_MUTATIONS_REJECTED", "result_sha256": digest(args.result),
              "mutations": []}
    for name in ("wrong_rotation", "wrong_normal_element_counter"):
        mutant = copy.deepcopy(original)
        if name == "wrong_rotation":
            cell = mutant["controls"][0]["rotations"][1]
            cell["normal_code"] = str(int(cell["normal_code"]) ^ 1)
        else:
            mutant["normal_element_search_counter"] += 1
        with tempfile.TemporaryDirectory(prefix="normal-barrel-mutation-") as tmp:
            tmpdir = Path(tmp)
            mutated_path = tmpdir / "mutated.json"
            verifier_output = tmpdir / "accepted.json"
            mutated_path.write_text(json.dumps(mutant, sort_keys=True, indent=2) + "\n")
            command = [SAGE, "-python", str(HERE / "verify_sage.py"),
                       "--result", str(mutated_path),
                       "--runtime-info", str(args.runtime_info),
                       "--out", str(verifier_output)]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=180)
            if proc.returncode == 0 or verifier_output.exists():
                raise AssertionError(f"independent Sage accepted {name}")
            report["mutations"].append({
                "name": name, "mutated_result_sha256": digest(mutated_path),
                "verifier_exit_code": proc.returncode,
                "verifier_output_written": False,
                "stderr_tail": proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "",
            })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
