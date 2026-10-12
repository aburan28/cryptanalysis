#!/usr/bin/env python3
"""Compile pinned WDSat with bounds computed from the width-four Q1460 XCNFs."""
from __future__ import annotations
import collections
import gzip
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")
TEMP = Path("/private/tmp/q1460_wdsat_build")
sys.path.insert(0, str(PARENT / "q20261011_wdsat_bridge"))
from build import instrument_search, patch_quadratic_undo_storage  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sizes(raw: bytes) -> dict:
    lines = raw.splitlines()
    header = lines[0].split()
    assert header[:2] == [b"p", b"cnf"]
    variables, rows = map(int, header[2:])
    cnf = xor = cnf_occ = xor_occ = implications = max_cnf = max_xor = 0
    widths = collections.Counter()
    for line in lines[1:]:
        tokens = line.split()
        assert tokens[-1] == b"0"
        width = len(tokens) - 1
        if tokens[0].startswith(b"x"):
            xor += 1; xor_occ += width; max_xor = max(max_xor, width)
        else:
            assert 1 <= width <= 4
            cnf += 1; cnf_occ += width; max_cnf = max(max_cnf, width)
            widths[width] += 1
            implications += width * (width - 1)
    assert cnf + xor == rows
    return {"variables": variables, "cnf_clauses": cnf, "xor_rows": xor,
            "cnf_occurrences": cnf_occ, "xor_occurrences": xor_occ,
            "cnf_implication_slots": implications,
            "max_cnf_width": max_cnf, "max_xor_width": max_xor,
            "cnf_widths": dict(sorted(widths.items()))}


def main() -> None:
    assert not TEMP.exists() and not (HERE / "build_receipt.json").exists()
    freeze = json.loads((HERE / "freeze.json").read_text())
    prepared = json.loads((HERE / "prepare_receipt.json").read_text())
    assert freeze["build_source_sha256"] == sha(Path(__file__))
    assert freeze["prepare_receipt_sha256"] == sha(HERE / "prepare_receipt.json")
    assert freeze["shared_patch_source_sha256"] == sha(PARENT / "q20261011_wdsat_bridge/build.py")
    TEMP.mkdir()
    output = {"proposal_id": "Q1460", "candidate_id": None,
              "freeze_sha256": sha(HERE / "freeze.json"),
              "upstream_commit": freeze["upstream_commit"],
              "architecture": platform.machine(), "os": platform.platform(),
              "compiler": subprocess.check_output(["gcc", "--version"],
                                                  text=True).splitlines()[0],
              "per_degree": {}}
    for degree in ("n83", "n53"):
        cells = [cell for cell in prepared["cells"] if cell.startswith(degree)]
        inputs = []
        for cell in cells:
            archive = (HERE / f"{cell}.xcnf.gz").read_bytes()
            assert hashlib.sha256(archive).hexdigest() == prepared["cells"][cell]["derived_archive_sha256"]
            raw = gzip.decompress(archive)
            assert hashlib.sha256(raw).hexdigest() == prepared["cells"][cell]["derived_raw_sha256"]
            inputs.append(sizes(raw))
        caps = {"MAX_ID": max(s["variables"] for s in inputs),
                "MAX_BUFFER_SIZE": max(max(s["cnf_occurrences"] + s["xor_occurrences"],
                                            s["cnf_implication_slots"]) for s in inputs) + 10000,
                "MAX_EQ": max(s["cnf_clauses"] + s["xor_rows"] for s in inputs) + 2,
                "MAX_EQ_SIZE": max(max(s["max_cnf_width"], s["max_xor_width"])
                                   for s in inputs) + 2,
                "MAX_XEQ": max(s["xor_rows"] for s in inputs) + 2,
                "MAX_XEQ_SIZE": max(s["max_xor_width"] for s in inputs) + 2}
        dest = TEMP / degree
        shutil.copytree(UPSTREAM / "src", dest / "src")
        config = dest / "src/config.h"
        config.write_text("/* Q1460 generated exact width-four CNF-XOR limits. */\n" +
                          "\n".join(f"#define __{key}__ {value}" for key, value in caps.items()) + "\n")
        patch = patch_quadratic_undo_storage(dest / "src")
        markers = instrument_search(dest / "src")
        make = subprocess.run(["make", "-f", "makefile"], cwd=dest / "src",
                              capture_output=True, text=True)
        (HERE / f"build_{degree}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{degree}.stderr.txt").write_text(make.stderr)
        binary = dest / "wdsat_solver"
        output["per_degree"][degree] = {
            "config": caps, "config_sha256": sha(config),
            "input_sizes": inputs, "storage_patch": patch,
            "search_markers": markers, "return_code": make.returncode,
            "binary_path": str(binary) if binary.exists() else None,
            "binary_sha256": sha(binary) if binary.exists() else None,
            "stdout_sha256": sha(HERE / f"build_{degree}.stdout.txt"),
            "stderr_sha256": sha(HERE / f"build_{degree}.stderr.txt")}
        print(degree, "BUILT" if make.returncode == 0 else "BUILD_FAILED")
    (HERE / "build_receipt.json").write_text(json.dumps(output, indent=2,
                                                        sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
