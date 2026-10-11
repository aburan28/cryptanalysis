"""Confirm that independent Sage replay rejects altered field and group evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAGE = Path("/Volumes/SSD990/cryptanalysis/sage")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    result = json.loads((run_dir / "result.json").read_text())
    receipt = {}
    for name in ("field_witness", "group_image"):
        altered = json.loads(json.dumps(result))
        if name == "field_witness":
            altered["positive"][0]["witnesses"][0]["mask"] ^= 1
        else:
            altered["group"][0]["frobenius_q"] = altered["group"][1]["source_q"]
        input_path = run_dir / f"mutation-{name}.json"
        stdout_path = run_dir / f"mutation-{name}.stdout"
        stderr_path = run_dir / f"mutation-{name}.stderr"
        output_path = run_dir / f"mutation-{name}-verification.json"
        for path in (input_path, stdout_path, stderr_path, output_path):
            if path.exists():
                raise SystemExit(f"refusing to overwrite {path}")
        input_path.write_text(json.dumps(altered, sort_keys=True, indent=2) + "\n")
        command = [str(SAGE), "-python", str(HERE / "verify_sage.py"),
                   "--result", str(input_path),
                   "--runtime-info", str(run_dir / "runtime-info.json"),
                   "--out", str(output_path)]
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                     timeout=180, check=False)
        if process.returncode == 0 or output_path.exists():
            raise AssertionError(f"altered {name} receipt was accepted")
        receipt[name] = {
            "mutated_result_sha256": sha256(input_path),
            "exit_code": process.returncode,
            "stdout_sha256": sha256(stdout_path),
            "stderr_sha256": sha256(stderr_path),
            "verifier_output_absent": True,
        }
    report = run_dir / "mutation-check.json"
    if report.exists():
        raise SystemExit(f"refusing to overwrite {report}")
    report.write_text(json.dumps({
        "status": "PASS_BOTH_MUTATIONS_REJECTED",
        "source_result_sha256": sha256(run_dir / "result.json"),
        "runtime_info_sha256": sha256(run_dir / "runtime-info.json"),
        "mutations": receipt,
    }, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
