#!/usr/bin/env python3
"""Confirm the independent XCNF verifier rejects a changed primary bit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-run-dir", type=Path, required=True)
    parser.add_argument("--witness-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("mutation receipt already exists")
    witness = json.loads((args.witness_dir / "receipt.json").read_text())
    packed = bytearray(gzip.decompress(
        (args.witness_dir / "assignment.bin.gz").read_bytes()))
    packed[0] ^= 1 << 1  # Wire 1: first target-fiber selector bit.
    with tempfile.TemporaryDirectory(prefix="orbit-w24-m5-mutation-") as temp:
        folder = Path(temp)
        mutated = folder / "witness"
        mutated.mkdir()
        compressed = mutated / "assignment.bin.gz"
        compressed.write_bytes(gzip.compress(bytes(packed), compresslevel=9, mtime=0))
        witness["raw_assignment_sha256"] = hashlib.sha256(packed).hexdigest()
        witness["compressed_assignment_sha256"] = digest(compressed)
        (mutated / "receipt.json").write_text(
            json.dumps(witness, indent=2, sort_keys=True) + "\n")
        verifier_out = folder / "verification.json"
        command = [sys.executable, str(HERE / "verify_xcnf.py"),
                   "--strict-run-dir", str(args.strict_run_dir.resolve()),
                   "--witness-dir", str(mutated),
                   "--out", str(verifier_out)]
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=60)
        if not verifier_out.exists():
            raise AssertionError("mutant produced no independent verifier receipt")
        verification = json.loads(verifier_out.read_text())
        if proc.returncode == 0 or verification["status"] != "FAIL_XCNF_ASSIGNMENT":
            raise AssertionError("changed target selector was accepted")
        if verification["violations"] < 1:
            raise AssertionError("changed selector caused no checked row violation")
        report = {
            "schema": "ecc2k130-orbit-w24-m5-sat-mutation-v1",
            "status": "PASS_MUTATED_SELECTOR_REJECTED",
            "candidate_id": None,
            "strict_result_sha256": digest(args.strict_run_dir / "receipt.json"),
            "original_witness_sha256": digest(args.witness_dir / "receipt.json"),
            "mutation": "flip packed assignment wire 1, first target-fiber selector",
            "mutated_assignment_sha256": hashlib.sha256(packed).hexdigest(),
            "verifier_exit_code": proc.returncode,
            "verifier_status": verification["status"],
            "violations": verification["violations"],
            "first_failure": verification["first_failure"],
            "verifier_source_sha256": digest(HERE / "verify_xcnf.py"),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"],
                      "violations": report["violations"]}, sort_keys=True))


if __name__ == "__main__":
    main()
