#!/usr/bin/env python3
"""Check deferred XYZZ against balanced XYZZ, Jacobian, and known points."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "prime-j0-secp256k1-native"
ORDER = int("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
MODES = {
    "jacobian": ("--scalar-unit-orbit-u14-jacobian-affine-control",
                 "unit_orbit_u14_jacobian_control"),
    "balanced": ("--scalar-unit-orbit-u14-xyzz-fixed",
                 "unit_orbit_u14_xyzz_fixed"),
    "deferred": ("--scalar-unit-orbit-u14-xyzz-deferred-fixed",
                 "unit_orbit_u14_xyzz_deferred_fixed"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(binary, args, input_text, output):
    process = subprocess.run([str(binary), *args], input=input_text, text=True,
                             capture_output=True, timeout=1200, check=False)
    output.write_text(process.stdout)
    output.with_suffix(output.suffix + ".stderr").write_text(process.stderr)
    assert process.returncode == 0, (args, process.returncode, process.stderr[-1000:])
    return process.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("output already exists")
    fixture_path = UPSTREAM / "tau6-comb13-bench-fixture.json"
    fixture = json.loads(fixture_path.read_text())
    cases = fixture["cases"]
    assert fixture["schema"] == 1 and len(cases) == 129
    generator = cases[0]["base_x_hex"] + ":" + cases[0]["base_y_hex"]
    boundaries = [(0, "identity"), (1, generator),
                  (ORDER, "identity"), (ORDER + 1, generator)]
    holdout = [int.from_bytes(hashlib.sha256(
        b"xyzz-deferred-v1:" + i.to_bytes(4, "big")).digest(), "big") % ORDER
        for i in range(512)]
    scalars = ([row["scalar_hex"] for row in cases]
               + [format(k, "064x") for k, _ in boundaries]
               + [format(k, "064x") for k in holdout])
    input_text = "".join(scalar + "\n" for scalar in scalars)
    input_path = output.with_name(output.stem + "-input.txt")
    input_path.write_text(input_text)
    results = {}
    raw_paths = {}
    for name, (flag, mode) in MODES.items():
        path = output.with_name(output.stem + "-" + name + "-raw.jsonl")
        lines = run(binary, [flag], input_text, path).splitlines()
        assert len(lines) == len(scalars), (name, len(lines), len(scalars))
        rows = [json.loads(line) for line in lines]
        assert all(row["mode"] == mode for row in rows), name
        results[name] = rows
        raw_paths[name] = path

    first = results["jacobian"]
    for index, (row, actual) in enumerate(zip(cases, first)):
        expected = ("identity" if row["expected_identity"] else
                    row["expected_x_hex"] + ":" + row["expected_y_hex"])
        assert actual["point"] == expected, ("fixture", index, actual["point"])
    for index, ((_, expected), actual) in enumerate(
        zip(boundaries, first[len(cases):len(cases) + len(boundaries)])):
        assert actual["point"] == expected, ("boundary", index, actual["point"])

    fields = ("point", "representative", "generic_additions", "retained_bytes")
    for name in ("balanced", "deferred"):
        for index, (control, actual) in enumerate(zip(first, results[name])):
            assert all(control[field] == actual[field] for field in fields), (
                name, index, {field: (control[field], actual[field]) for field in fields})
    assert sum(row["generic_additions"] for row in first[:len(cases)]) == 1677

    benchmark_paths = {}
    for name, flag, benchmark_mode in (
        ("jacobian", "--benchmark-scalar-unit-orbit-windows14-fixed-case",
         "unit_orbit_windows14_fixed"),
        ("balanced", "--benchmark-scalar-unit-orbit-u14-xyzz-fixed-case",
         "unit_orbit_u14_xyzz_fixed"),
        ("deferred", "--benchmark-scalar-unit-orbit-u14-xyzz-deferred-fixed-case",
         "unit_orbit_u14_xyzz_deferred_fixed"),
    ):
        path = output.with_name(output.stem + "-" + name + "-benchmark.txt")
        raw = run(binary, [flag, str(fixture_path), "0"], "", path)
        fields_out = dict(part.split("=", 1) for part in raw.split() if "=" in part)
        assert fields_out["verified"] == "1"
        assert fields_out["curve"] == "secp256k1"
        assert fields_out["mode"] == benchmark_mode
        assert fields_out["scalar"] == cases[0]["scalar_hex"]
        assert fields_out["base_x"] == cases[0]["base_x_hex"]
        assert fields_out["base_y"] == cases[0]["base_y_hex"]
        assert fields_out["point"] == first[0]["point"]
        assert int(fields_out["retained_bytes"]) == first[0]["retained_bytes"]
        assert float(fields_out["online_ms"]) > 0
        assert float(fields_out["preparation_ms"]) >= 0
        benchmark_paths[name] = path

    source_paths = [HERE / "Cargo.toml", HERE / "Cargo.lock", HERE / "build.rs",
                    HERE / "DEFERRED_PROTOCOL.md", HERE / "src/main.rs",
                    HERE / "src/xyzz_append.rs", HERE / "src/unit_orbit_append.rs",
                    HERE / "check_deferred_xyzz.py", UPSTREAM / "src/bin/eisenstein_fixed.rs",
                    UPSTREAM / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
                    HERE.parent.parent / "suite/src/ct_bignum.rs"]
    receipt = {
        "schema": 1,
        "status": "passed",
        "fixture_cases": len(cases),
        "boundary_cases": len(boundaries),
        "holdout_cases": len(holdout),
        "total_cases": len(scalars),
        "generic_additions_fixture_total": 1677,
        "retained_bytes": first[0]["retained_bytes"],
        "benchmark_dispatch_cases_per_mode": 1,
        "binary_sha256": sha(binary),
        "fixture_sha256": sha(fixture_path),
        "input_sha256": sha(input_path),
        "raw_output_sha256": {name: sha(path) for name, path in raw_paths.items()},
        "benchmark_output_sha256": {name: sha(path)
                                    for name, path in benchmark_paths.items()},
        "source_sha256": {str(path.relative_to(HERE.parent.parent)): sha(path)
                          for path in source_paths},
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "cpu_timing_used": False,
    }
    output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("status", "fixture_cases", "boundary_cases", "holdout_cases",
                       "total_cases")}, sort_keys=True))


if __name__ == "__main__":
    main()
