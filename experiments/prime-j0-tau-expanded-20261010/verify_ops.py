#!/usr/bin/env python3
"""Check exact point-kernel diagnostic counts and their raw log binding."""

from hashlib import sha256
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PATTERN = re.compile(
    r"^mode=(\w+) cases=(\d+) point_kernel_add=(\d+) point_kernel_sub=(\d+) "
    r"point_kernel_mul=(\d+) point_kernel_square=(\d+) gauge_rotations=(\d+)$", re.M)


def digest(data):
    return sha256(data).hexdigest()


def main():
    record = json.loads((HERE / "ops-diagnostic.json").read_text())
    log_raw = (HERE / "ops-diagnostic.log").read_bytes()
    assert digest(log_raw) == record["diagnostic_log_sha256"]
    assert digest((HERE / "ops-diagnostic.patch").read_bytes()) == record[
        "diagnostic_patch_sha256"]
    assert digest((HERE / "fresh-inputs.json").read_bytes()) == record[
        "fresh_input_sha256"]
    assert b"test result: ok. 1 passed; 0 failed;" in log_raw
    rows = {}
    for match in PATTERN.finditer(log_raw.decode()):
        rows[match.group(1)] = dict(zip(
            ("cases", "point_kernel_add", "point_kernel_sub", "point_kernel_mul",
             "point_kernel_square", "gauge_rotations"),
            map(int, match.groups()[1:])))
    assert rows == record["operations"]
    assert set(rows) == {"frontier19", "orbit_x", "tau_expanded"}
    assert all(row["cases"] == 4096 for row in rows.values())
    assert rows["frontier19"]["point_kernel_mul"] - rows["tau_expanded"][
        "point_kernel_mul"] == 40_697
    assert rows["orbit_x"]["point_kernel_mul"] - rows["tau_expanded"][
        "point_kernel_mul"] == 24_577
    assert rows["frontier19"]["point_kernel_square"] - rows["tau_expanded"][
        "point_kernel_square"] == 12_288
    print("tau_expanded_point_kernel_counts_verified=1 cases=4096 modes=3")


if __name__ == "__main__":
    main()
