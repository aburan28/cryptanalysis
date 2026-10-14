"""Run the independent packed-field host gate for selected CLMAD schedules."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[4]
HEADER = ROOT / "ecc2k130/runner/include/packed131.h"
TEST = ROOT / "ecc2k130/runner/src/testpacked.cpp"


def run(command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               timeout=180)
    return {"command": command, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}


def main(output_name: str, flag: str = "ECC_PACKED_CLMAD_HI_FIRST=1") -> None:
    output = Path(output_name)
    if output.exists():
        raise FileExistsError(output)
    if flag not in ("ECC_PACKED_CLMAD_HI_FIRST=1", "ECC_PACKED_CLMUL_HI_BATCH=1"):
        raise ValueError("unsupported candidate flag")
    with tempfile.TemporaryDirectory(prefix="ecc2k130-hi-first-") as directory:
        binary = Path(directory) / "testpacked"
        command = ["clang++", "-O2", "-std=c++17",
                   "-DECC_PACKED_SINGLE_PRODUCT=1", "-DECC_PACKED_BY_VALUE=1",
                   "-DECC_PACKED_PERM_SIGMA=3", "-DECC_PACKED_DIRECT_REDUCE=1",
                   "-DECC_PACKED_GENERATED_PRODUCT=1", "-DECC_PACKED_CLMAD=1",
                   f"-D{flag}", "-Wno-unknown-pragmas",
                   str(TEST.relative_to(ROOT)), "-o", str(binary)]
        receipt = {
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in (HEADER, TEST)},
            "compiler": run(["clang++", "--version"]),
            "build": run(command),
        }
        if receipt["build"]["returncode"] == 0:
            receipt["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
            receipt["run"] = run([str(binary)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2) + "\n")
    if receipt["build"]["returncode"] or receipt.get("run", {}).get("returncode"):
        raise SystemExit(1)
    print(json.dumps({"receipt": str(output), "outcome": "passed"}))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: host_gate.py output.json [CANDIDATE_FLAG=1]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "ECC_PACKED_CLMAD_HI_FIRST=1")
