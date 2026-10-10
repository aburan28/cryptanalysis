#!/usr/bin/env python3
"""Verify the temporary field counters against an independent atlas decode."""

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

from run_replay import HERE, parse
from verify_inputs import main as verify_inputs


ROOT = HERE.parent.parent
SOURCE = HERE.parent / "prime-j0-tau-power16-20261010/screen.py"
spec = importlib.util.spec_from_file_location("tau_power16_screen", SOURCE)
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)
NAMES = ("frontier15_budget_gauge", "frontier15_bound_budget",
         "frontier16_beta_solinas")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def atlas(path):
    raw = path.read_bytes()
    assert raw[:3] == b"T2B"
    width = raw[3] - ord("0")
    radix = 1 << width
    seeds_start = 8 + 4 * radix * radix
    count = struct.unpack_from("<I", raw, 4)[0]
    assert len(raw) == seeds_start + 4 * count
    seeds = [struct.unpack_from("<hh", raw, seeds_start + 4 * i)
             for i in range(count)]
    return raw, radix, seeds


def operation_counts(scalars):
    full8 = atlas(HERE.parent / "prime-j0-tau-frontier-20261010/w8-d256/atlas-w8.bin")
    full9 = atlas(HERE.parent / "prime-j0-bound-budget15-20261010/atlas-w9.bin")
    final9 = atlas(HERE.parent / "prime-j0-tau-power16-20261010/atlas-w9.bin")
    schedule = [full8] * 6 + [full9] * 8 + [final9]
    mixed = per_term = gauge = 0
    for text in scalars:
        a, b = screen.representative(int(text, 16) % screen.ORDER)
        selected = 0
        classes = [set(), set()]
        for raw, radix, seeds in schedule:
            slot = (a % radix) * radix + b % radix
            code = struct.unpack_from("<I", raw, 8 + 4 * slot)[0]
            digit, exponent = screen.digit_from_code(code, seeds)
            assert (digit[0] % radix, digit[1] % radix) == (a % radix, b % radix)
            a = (a - digit[0]) // radix
            b = (b - digit[1]) // radix
            if code >> 4:
                selected += 1
                power = (code & 7) // 2
                per_term += power != 0
                classes[exponent].add(power)
        assert (a, b) == (0, 0)
        mixed += max(0, selected - 1)
        for powers in classes:
            order = [power for power in (1, 2, 0) if power in powers]
            if order:
                gauge += len(order) - 1 + (order[-1] != 0)
    return {"mixed_additions": mixed, "per_term_rotations": per_term,
            "gauge_rotations": gauge}


def main():
    verify_inputs()
    parent = json.loads((HERE.parent / "prime-j0-bound-budget15-20261010/source-receipt.json").read_text())
    assert digest(SOURCE) == parent["source_sha256"]["experiments/prime-j0-tau-power16-20261010/screen.py"]
    source = json.loads((HERE / "source-receipt.json").read_text())
    replay = json.loads((HERE / "replay-result.json").read_text())
    assert source["source_freeze_commit"] == replay["source_freeze_commit"]
    patch = HERE / "ops-diagnostic.patch"
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=ROOT,
                   check=True, capture_output=True)
    inputs = HERE / "fresh-inputs.json"
    scalars = json.loads(inputs.read_text())["scalars_hex"]
    assert len(scalars) == 4096
    counts = operation_counts(scalars)
    log = HERE / "ops-diagnostic.log"
    lines = log.read_text().splitlines()
    assert any("test result: ok. 1 passed" in line for line in lines)
    records = {row["mode"]: row for line in lines if line.startswith("mode=")
               for row in [parse(line)]}
    assert set(records) == set(NAMES)
    for name in NAMES:
        row = records[name]
        assert int(row["cases"]) == 4096
        products = 36 * (int(row["point_kernel_generic_mul"]) +
                         int(row["point_kernel_square"])) + 23 * int(row["point_kernel_solinas_mul"])
        assert products == int(row["source_limb_products"])
    assert int(records[NAMES[0]]["mixed_additions"]) == counts["mixed_additions"]
    assert int(records[NAMES[1]]["mixed_additions"]) == counts["mixed_additions"]
    assert int(records[NAMES[0]]["point_kernel_solinas_mul"]) == counts["gauge_rotations"]
    assert int(records[NAMES[1]]["point_kernel_solinas_mul"]) == counts["per_term_rotations"]
    for field in ("mixed_additions", "point_kernel_generic_mul", "point_kernel_square"):
        assert records[NAMES[0]][field] == records[NAMES[1]][field]
    saved = int(records[NAMES[1]]["source_limb_products"]) - int(records[NAMES[0]]["source_limb_products"])
    assert saved == 23 * (counts["per_term_rotations"] - counts["gauge_rotations"]) > 0
    receipt = {"schema": 1, "source_freeze_commit": source["source_freeze_commit"],
               "fresh_input_sha256": digest(inputs), "patch_sha256": digest(patch),
               "log_sha256": digest(log), "independent_counts": counts,
               "source_limb_products_saved_vs_mode156": saved, "modes": records}
    destination = HERE / "ops-diagnostic.json"
    if sys.argv[1:] == ["--write"]:
        assert not destination.exists()
        destination.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        assert json.loads(destination.read_text()) == receipt
    print(f"ops_verified=1 cases=4096 saved_vs_mode156={saved}")


if __name__ == "__main__":
    main()
