#!/usr/bin/env python3
"""Bind the targeted native point replay to its executable and raw log."""

from hashlib import sha256
import gzip
import argparse
import json
from pathlib import Path
import platform
import re
import subprocess


HERE = Path(__file__).resolve().parent
WINDOW = Path("src/bin/eisenstein_fixed/unit_orbit_windows.rs")
MAIN = Path("src/bin/eisenstein_fixed.rs")
TEST = "phase_optimal_tau_cover_matches_disjoint_holdout_and_binary_points"
LINE = re.compile(
    r"phase_optimal_tau_cases=(\d+) active_rho=(\d+) rho_terms=(\d+) "
    r"additions=(\d+) gauge_products=(\d+) retained_bytes=(\d+)")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_root", type=Path)
    args = parser.parse_args()
    native = args.native_root.resolve()
    material = json.loads((HERE / "native-materialization.json").read_bytes())
    for name, expected in material["generated_sha256"].items():
        assert digest(native / name) == expected, name
    for name, expected in material["assets_sha256"].items():
        assert digest(native / name) == expected, name
    log_archive = HERE / "native-targeted.log.gz"
    log_raw = gzip.decompress(log_archive.read_bytes())
    log = log_raw.decode()
    found = LINE.search(log)
    assert found is not None
    values = tuple(map(int, found.groups()))
    assert values == (4096, 0, 0, 49152, 18077, 59032928)
    assert f"test unit_orbit_windows::tests::{TEST} ... ok" in log
    assert "test result: ok. 1 passed; 0 failed" in log
    run = re.search(r"Running unittests .*\((target/release/deps/eisenstein_fixed-[0-9a-f]+)\)", log)
    assert run is not None
    executable = native / run.group(1)
    assert executable.is_file()
    receipt = {"schema": 1, "status": "passed",
               "test": TEST, "cases": values[0], "active_rho": values[1],
               "rho_terms": values[2], "additions": values[3],
               "gauge_products": values[4], "retained_bytes": values[5],
               "independent_binary_points": 128,
               "platform": platform.platform(), "machine": platform.machine(),
               "rustc": subprocess.check_output(["rustc", "--version"],
                                                text=True).strip(),
               "binary_sha256": digest(executable),
               "generated_sha256": {str(path): digest(native / path)
                                    for path in (WINDOW, MAIN)},
               "atlas_sha256": digest(native / "atlas-r1024-full-dual-rho0.bin"),
               "input_sha256": digest(HERE / "holdout-inputs.json"),
               "paths_sha256": digest(HERE / "holdout-paths.jsonl"),
               "raw_log_sha256": sha256(log_raw).hexdigest(),
               "raw_log_archive_sha256": digest(log_archive),
               "collector_sha256": digest(Path(__file__))}
    (HERE / "native-targeted-check.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "cases", "gauge_products", "retained_bytes",
                       "binary_sha256")}, sort_keys=True))


if __name__ == "__main__":
    main()
