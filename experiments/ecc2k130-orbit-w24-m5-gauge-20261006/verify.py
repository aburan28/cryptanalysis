#!/usr/bin/env python3
"""Independently audit the exact eight-clause gauge and every XCNF row."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-orbit-w24-m5-sat-20261006"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def xcnf_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == ".gz" else data


def check_rows(lines: list[str], assignment: bytes, variables: int) -> tuple[int, int, int]:
    def truth(literal: int) -> bool:
        wire = abs(literal)
        if not 1 <= wire <= variables:
            raise ValueError(f"wire {wire} outside header")
        value = bool((assignment[wire >> 3] >> (wire & 7)) & 1)
        return value if literal > 0 else not value

    cnf = xors = violations = 0
    for line in lines:
        words = line.split()
        xor = words[0] == "x"
        values = words[1:] if xor else words
        if not values or values[-1] != "0":
            raise ValueError("unterminated XCNF row")
        literals = [int(word) for word in values[:-1]]
        if not literals or 0 in literals:
            raise ValueError("empty or malformed XCNF row")
        if xor:
            xors += 1
            satisfied = sum(truth(literal) for literal in literals) % 2 == 1
        else:
            cnf += 1
            satisfied = any(truth(literal) for literal in literals)
        violations += not satisfied
    return cnf, xors, violations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("verification receipt already exists")
    config = read(HERE / "CONFIG.json")
    build_path = args.primary_dir / "build.json"
    build = read(build_path)
    strict_path = PARENT / "runs/planted-r2/receipt.json"
    strict = read(strict_path)
    parent_archive = PARENT / "runs/planted-r2/system.xcnf.gz"
    assignment_archive = PARENT / "runs/witness-r2/assignment.bin.gz"
    parent_verification_path = PARENT / "runs/witness-r2/verification-archived.json"
    parent_verification = read(parent_verification_path)
    for key, path in (
        ("parent_ungauged_receipt_sha256", strict_path),
        ("parent_ungauged_xcnf_gzip_sha256", parent_archive),
        ("parent_known_assignment_gzip_sha256", assignment_archive),
        ("parent_known_assignment_verification_sha256", parent_verification_path),
    ):
        require(digest(path) == config[key], f"frozen parent changed: {key}")
    require(parent_verification["status"] == "PASS_KNOWN_PLANTED_XCNF_ASSIGNMENT",
            "parent known witness not verified")
    require(build["config_sha256"] == digest(HERE / "CONFIG.json") and
            build["parent_receipt_sha256"] == digest(strict_path),
            "gauged build not bound to frozen inputs")
    new_path = args.primary_dir / "system.xcnf"
    if not new_path.exists():
        new_path = args.primary_dir / "system.xcnf.gz"
    old_raw = xcnf_bytes(parent_archive)
    new_raw = xcnf_bytes(new_path)
    require(hashlib.sha256(old_raw).hexdigest() ==
            strict["xcnf_sha256"] == config["parent_ungauged_xcnf_sha256"],
            "parent raw XCNF changed")
    require(hashlib.sha256(new_raw).hexdigest() == build["xcnf_sha256"],
            "gauged raw XCNF changed")
    old = old_raw.decode("ascii").splitlines(keepends=True)
    new = new_raw.decode("ascii").splitlines(keepends=True)
    n = strict["variables"]
    c = strict["cnf_clauses"]
    x = strict["xor_rows"]
    wires = build["first_exponent_wires"]
    require(len(wires) == 8 and len(set(wires)) == 8 and all(1 <= w <= n for w in wires),
            "invalid first exponent wire list")
    require(old[0] == f"p cnf {n} {c+x}\n" and len(old) == 1+c+x,
            "parent XCNF header or row count changed")
    require(new[0] == f"p cnf {n} {c+x+8}\n" and len(new) == 1+c+x+8,
            "gauged XCNF header or row count changed")
    require(new[1:1+c] == old[1:1+c], "original CNF rows changed")
    require(new[1+c:1+c+8] == [f"-{wire} 0\n" for wire in wires],
            "gauge differs from eight zero unit clauses")
    require(new[1+c+8:] == old[1+c:], "original XOR rows changed")
    assignment = gzip.decompress(assignment_archive.read_bytes())
    raw_assignment_hash = hashlib.sha256(assignment).hexdigest()
    require(raw_assignment_hash == parent_verification["assignment_sha256"],
            "known assignment changed")
    counts = check_rows(new[1:], assignment, n)
    require(counts == (c+8, x, 0), "known planted assignment violates gauged XCNF")
    mutated = bytearray(assignment)
    wire = wires[0]
    mutated[wire >> 3] ^= 1 << (wire & 7)
    mutation_counts = check_rows(new[1:], mutated, n)
    require(mutation_counts[2] > 0, "flipped gauge bit was not rejected")
    report = {
        "schema": "ecc2k130-orbit-w24-m5-gauge-verification-v1",
        "status": "PASS_EXACT_EIGHT_CLAUSE_GAUGE_AND_KNOWN_WITNESS",
        "candidate_id": None,
        "config_sha256": digest(HERE / "CONFIG.json"),
        "build_receipt_sha256": digest(build_path),
        "parent_verification_sha256": digest(parent_verification_path),
        "parent_xcnf_sha256": hashlib.sha256(old_raw).hexdigest(),
        "gauged_xcnf_sha256": hashlib.sha256(new_raw).hexdigest(),
        "gauged_xcnf_archive_sha256": digest(new_path) if new_path.suffix == ".gz" else None,
        "known_assignment_sha256": raw_assignment_hash,
        "first_exponent_wires": wires,
        "variables": n,
        "cnf_clauses": counts[0],
        "xor_rows": counts[1],
        "known_assignment_violations": counts[2],
        "flipped_first_exponent_bit_violations": mutation_counts[2],
        "verifier_source_sha256": digest(Path(__file__)),
        "unknown_witness_recovered": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
