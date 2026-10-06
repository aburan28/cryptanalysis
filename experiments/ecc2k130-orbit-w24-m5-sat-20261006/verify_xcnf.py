#!/usr/bin/env python3
"""Independently check every native-XOR and CNF row of the planted formula."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-run-dir", type=Path, required=True)
    parser.add_argument("--witness-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification output already exists")
    strict_path = args.strict_run_dir / "receipt.json"
    witness_path = args.witness_dir / "receipt.json"
    strict = json.loads(strict_path.read_text())
    witness = json.loads(witness_path.read_text())
    xcnf = args.strict_run_dir / "system.xcnf"
    packed_gz = args.witness_dir / "assignment.bin.gz"
    assert digest(xcnf) == strict["xcnf_sha256"] == witness["xcnf_sha256"]
    assert digest(packed_gz) == witness["compressed_assignment_sha256"]
    raw = gzip.decompress(packed_gz.read_bytes())
    assert len(raw) == witness["raw_assignment_bytes"]
    assert hashlib.sha256(raw).hexdigest() == witness["raw_assignment_sha256"]
    assert witness["strict_result_sha256"] == digest(strict_path)

    def truth(literal: int) -> bool:
        wire = abs(literal)
        if not 1 <= wire <= strict["variables"]:
            raise ValueError(f"wire {wire} outside XCNF header")
        value = bool((raw[wire >> 3] >> (wire & 7)) & 1)
        return value if literal > 0 else not value

    header = None
    clauses = xors = violations = 0
    first_failure = None
    with xcnf.open(encoding="ascii") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line or line.startswith("c "):
                continue
            if line.startswith("p "):
                if header is not None:
                    raise ValueError("multiple XCNF headers")
                parts = line.split()
                if len(parts) != 4 or parts[:2] != ["p", "cnf"]:
                    raise ValueError("malformed XCNF header")
                header = (int(parts[2]), int(parts[3]))
                continue
            if header is None:
                raise ValueError("XCNF row preceded header")
            is_xor = line.startswith("x ")
            words = line.split()[1:] if is_xor else line.split()
            if not words or words[-1] != "0":
                raise ValueError(f"unterminated XCNF row {line_number}")
            literals = [int(word) for word in words[:-1]]
            if 0 in literals:
                raise ValueError(f"zero inside XCNF row {line_number}")
            if is_xor:
                xors += 1
                satisfied = sum(truth(literal) for literal in literals) % 2 == 1
            else:
                clauses += 1
                satisfied = any(truth(literal) for literal in literals)
            if not satisfied:
                violations += 1
                if first_failure is None:
                    first_failure = {"line_number": line_number,
                                     "kind": "xor" if is_xor else "cnf"}
    if header != (strict["variables"], strict["cnf_clauses"] + strict["xor_rows"]):
        raise ValueError("XCNF header differs from strict receipt")
    if clauses != strict["cnf_clauses"] or xors != strict["xor_rows"]:
        raise ValueError("XCNF row totals differ from strict receipt")
    report = {
        "schema": "ecc2k130-orbit-w24-m5-sat-xcnf-verification-v1",
        "status": "PASS_KNOWN_PLANTED_XCNF_ASSIGNMENT" if violations == 0 else "FAIL_XCNF_ASSIGNMENT",
        "candidate_id": None,
        "strict_result_sha256": digest(strict_path),
        "witness_result_sha256": digest(witness_path),
        "xcnf_sha256": digest(xcnf),
        "assignment_sha256": hashlib.sha256(raw).hexdigest(),
        "variables": strict["variables"],
        "cnf_clauses": clauses,
        "xor_rows": xors,
        "violations": violations,
        "first_failure": first_failure,
        "verifier_source_sha256": digest(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if violations:
        raise SystemExit(1)
    print(json.dumps({key: report[key] for key in
                      ("status", "variables", "cnf_clauses", "xor_rows", "violations")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
