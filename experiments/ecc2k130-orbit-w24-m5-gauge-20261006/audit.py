#!/usr/bin/env python3
"""Read-only audit of the archived gauge build, known witness, and two SAT runs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("audit output already exists")
    config = read(HERE / "CONFIG.json")
    primary = HERE / "runs/primary"
    secondary = HERE / "runs/secondary"
    build_path = primary / "build.json"
    build = read(build_path)
    verification_path = primary / "verification.json"
    verification = read(verification_path)
    require(build["status"] == "PASS_EXACT_PARENT_PLUS_EIGHT_UNIT_CLAUSES" and
            build["config_sha256"] == digest(HERE / "CONFIG.json") and
            build["source_sha256"] == digest(HERE / "gauge.py") and
            build["runtime_info_sha256"] == digest(primary / "runtime-info.json"),
            "build provenance failed")
    require(build["parent_receipt_sha256"] ==
            digest(PARENT / "runs/planted-r2/receipt.json") ==
            config["parent_ungauged_receipt_sha256"], "parent receipt changed")
    require(build["parent_xcnf_sha256"] == config["parent_ungauged_xcnf_sha256"],
            "parent XCNF changed")
    require(build["variables"] == 142303 and build["cnf_clauses"] == 239947 and
            build["xor_rows"] == 61519 and len(build["first_exponent_wires"]) == 8,
            "gauged formula shape changed")
    xcnf_path = primary / "system.xcnf.gz"
    xcnf_raw = gzip.decompress(xcnf_path.read_bytes())
    require(hashlib.sha256(xcnf_raw).hexdigest() == build["xcnf_sha256"] and
            len(xcnf_raw) == build["xcnf_bytes"], "archived gauged formula changed")
    require(verification["status"] ==
            "PASS_EXACT_EIGHT_CLAUSE_GAUGE_AND_KNOWN_WITNESS" and
            verification["build_receipt_sha256"] == digest(build_path) and
            verification["config_sha256"] == digest(HERE / "CONFIG.json") and
            verification["gauged_xcnf_sha256"] == build["xcnf_sha256"] and
            verification["gauged_xcnf_archive_sha256"] == digest(xcnf_path) and
            verification["variables"] == build["variables"] and
            verification["cnf_clauses"] == build["cnf_clauses"] and
            verification["xor_rows"] == build["xor_rows"] and
            verification["known_assignment_violations"] == 0 and
            verification["flipped_first_exponent_bit_violations"] > 0 and
            verification["verifier_source_sha256"] == digest(HERE / "verify.py"),
            "independent formula or witness audit failed")
    runs = {}
    for tier, directory, limit, wall in (
        ("primary", primary, config["primary_conflicts"], config["primary_wall_seconds"]),
        ("secondary", secondary, config["secondary_conflicts"],
         config["secondary_wall_seconds"]),
    ):
        receipt_path = directory / "receipt.json"
        receipt = read(receipt_path)
        command = receipt["solver_command"]
        expected_command = [
            config["solver_binary"], f"--maxtime={wall}",
            f"--maxconfl={limit}", f"--threads={config['solver_threads']}",
            f"--random={config['solver_seed']}", "--maxsol=1", "--printsol=1",
        ]
        require(receipt["tier"] == tier and receipt["status"] == "unresolved" and
                receipt["solver_status"] == "INDETERMINATE" and
                receipt["solver_exit_code"] == 15 and receipt["model"] is None and
                receipt["independently_verified_unknown_witness"] is False and
                receipt["monitor_error"] is None and
                0 < receipt["solver_peak_rss_bytes"] <= config["peak_rss_limit_bytes"] and
                receipt["conflict_limit"] == limit and
                receipt["wall_limit_seconds"] == wall and
                len(command) == 8 and command[:7] == expected_command and
                Path(command[7]).name == "system.xcnf" and
                receipt["solver_binary_sha256"] == config["solver_binary_sha256"] and
                receipt["solver_conflicts_reported"] == limit + 1 and
                receipt["config_sha256"] == digest(HERE / "CONFIG.json") and
                receipt["source_sha256"] == digest(HERE / "gauge.py") and
                receipt["build_receipt_sha256"] == digest(build_path) and
                receipt["xcnf_sha256"] == build["xcnf_sha256"] and
                receipt["parent_ungauged_xcnf_sha256"] ==
                config["parent_ungauged_xcnf_sha256"] and
                receipt["public_q"] == config["public_q"] and
                receipt["variables"] == build["variables"] and
                receipt["cnf_clauses"] == build["cnf_clauses"] and
                receipt["xor_rows"] == build["xor_rows"] and
                receipt["target_online_ms"] is None and
                receipt["natural_pdp_yield"] is None and
                receipt["rho_ratio"] is None,
                f"{tier} bounded result or null accounting changed")
        require(receipt["runtime_info_sha256"] ==
                digest(directory / "runtime-info.json"),
                f"{tier} Sage runtime changed")
        stdout_archive = directory / "solver.stdout.txt.gz"
        stdout = gzip.decompress(stdout_archive.read_bytes())
        require(hashlib.sha256(stdout).hexdigest() == receipt["solver_stdout_sha256"] and
                digest(directory / "solver.stderr.txt") == receipt["solver_stderr_sha256"],
                f"{tier} solver stream changed")
        text = stdout.decode("utf-8", errors="replace")
        conflicts = re.findall(r"^c conflicts\s*:\s*(\d+)", text, re.MULTILINE)
        require("s INDETERMINATE" in text and conflicts and
                int(conflicts[-1]) == limit + 1 and not re.search(r"^v ", text, re.MULTILINE),
                f"{tier} raw stream disagrees with receipt")
        runs[tier] = {
            "receipt_sha256": digest(receipt_path),
            "runtime_info_sha256": digest(directory / "runtime-info.json"),
            "solver_stdout_gzip_sha256": digest(stdout_archive),
            "solver_stdout_raw_sha256": hashlib.sha256(stdout).hexdigest(),
            "solver_stdout_raw_bytes": len(stdout),
            "solver_conflicts_reported": limit + 1,
            "solver_peak_rss_bytes": receipt["solver_peak_rss_bytes"],
            "solver_seconds_exploratory": receipt["solver_seconds_exploratory"],
        }
    report = {
        "schema": "ecc2k130-orbit-w24-m5-gauge-archive-audit-v1",
        "status": "PASS_BOUNDED_GAUGE_SEARCH_WITH_NO_MODEL",
        "candidate_id": None,
        "config_sha256": digest(HERE / "CONFIG.json"),
        "build_receipt_sha256": digest(build_path),
        "verification_sha256": digest(verification_path),
        "gauged_xcnf_sha256": build["xcnf_sha256"],
        "gauged_xcnf_gzip_sha256": digest(xcnf_path),
        "gauged_xcnf_raw_bytes": len(xcnf_raw),
        "runs": runs,
        "unknown_witness_recovered": False,
        "ordinary_target_attempted": False,
        "verifier_source_sha256": digest(Path(__file__)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["status"])


if __name__ == "__main__":
    main()
