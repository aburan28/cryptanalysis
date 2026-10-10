#!/usr/bin/env python3
"""Rebuild, verify, and prepare a U14 comparison on one Linux host.

The receipt is produced from this host's executable and outputs. The older
macOS resource logs are deliberately outside its source and result set.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
NATIVE = ROOT / "experiments/prime-j0-secp256k1-native"
FIXTURE = NATIVE / "tau6-comb13-bench-fixture.json"
BASE_SOURCE_PATHS = (
    HERE / "host_replay.py",
    HERE / "README.md",
    ROOT / "scripts/isolated_bench.py",
    ROOT / "experiments/prime-j0-u256-point-20261010/PROTOCOL.md",
    ROOT / "experiments/prime-j0-u256-point-20261010/PROOF.md",
    ROOT / "experiments/prime-j0-u256-point-20261010/fresh-inputs.json",
    ROOT / "experiments/prime-j0-u256-point-20261010/check_algebra.py",
    NATIVE / "Cargo.toml",
    NATIVE / "Cargo.lock",
    NATIVE / "src/bin/eisenstein_fixed.rs",
    NATIVE / "src/bin/eisenstein_fixed/unit_orbit_windows.rs",
    ROOT / "suite/src/ct_bignum.rs",
    FIXTURE,
)
GAUGE_SOURCE_PATHS = (
    ROOT / "experiments/prime-j0-u14-gauge-20261010/PROTOCOL.md",
    ROOT / "experiments/prime-j0-u14-gauge-20261010/PROOF.md",
    ROOT / "experiments/prime-j0-u14-gauge-20261010/fresh-inputs.json",
    ROOT / "experiments/prime-j0-u14-gauge-20261010/check_algebra.py",
    ROOT / "experiments/prime-j0-u14-gauge-20261010/make_inputs.py",
    ROOT / "experiments/prime-j0-u14-gauge-20261010/verify_candidate.py",
)
ARITHMETIC_SOURCE_PATHS = (
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/PROTOCOL.md",
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/PROOF.md",
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/ISOLATED_PANEL.md",
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/fresh-inputs.json",
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/make_inputs.py",
    ROOT / "experiments/prime-j0-arithmetic-atlas-20261010/verify_candidate.py",
)
FORMULA_SOURCE_PATHS = (
    ROOT / "experiments/prime-j0-formula-atlas-20261010/PROTOCOL.md",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/PROOF.md",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/ISOLATED_PANEL.md",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/fresh-inputs.json",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/make_inputs.py",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/verify_candidate.py",
    ROOT / "experiments/prime-j0-formula-atlas-20261010/runpod_correctness.sh",
)
COMPARISONS = {
    "point": {
        "modes": (
            ("reference", "unit_orbit_direct_limb14_fixed", "direct-limb"),
            ("candidate", "unit_orbit_u256_point14_fixed", "u256-point"),
        ),
        "retained_bytes": {"reference": 78_470_208, "candidate": 70_430_960},
        "native_tests": 85,
        "algebra": ROOT / "experiments/prime-j0-u256-point-20261010/check_algebra.py",
        "comparison_kind": "single-public-scalar-u14-eisenstein-vs-four-limb-point",
        "boundary": (
            "After fixture loading, scalar decoding, and both U14 table preparations. "
            "Includes scalar reduction, certified Voronoi selection, recoding, "
            "orbit lookup, unit actions, mixed point additions, final inversion, "
            "affine formatting, and expected-point verification."
        ),
    },
    "gauge": {
        "modes": (
            ("reference", "unit_orbit_u256_point14_fixed", "u256-point"),
            ("candidate", "unit_orbit_u256_gauge14_fixed", "u256-gauge"),
        ),
        "retained_bytes": {"reference": 70_430_960, "candidate": 70_430_960},
        "native_tests": 85,
        "algebra": ROOT / "experiments/prime-j0-u14-gauge-20261010/check_algebra.py",
        "comparison_kind": "single-public-scalar-u14-grouped-unit-gauge-vs-direct-unit",
        "boundary": (
            "Starts after fixture loading, scalar decoding, U14 point-table preparation, "
            "field and unit constants, and binary-inverse correction setup. Includes scalar "
            "reduction, certified Voronoi selection, signed-word recoding, choice staging, "
            "orbit lookups, unit or accumulator-gauge actions, mixed additions, final "
            "inversion, affine formatting, and expected-point verification. Stops after "
            "that verification."
        ),
    },
    "arithmetic": {
        "modes": (
            ("reference", "unit_orbit_u256_gauge14_fixed", "u256-gauge"),
            ("candidate", "unit_orbit_u256_arithmetic14_fixed", "u256-arithmetic"),
        ),
        "retained_bytes": {"reference": 70_430_960, "candidate": 65_188_008},
        "native_tests": 85,
        "algebra": ROOT / "experiments/prime-j0-u14-gauge-20261010/check_algebra.py",
        "comparison_kind": "single-public-scalar-u14-arithmetic-orbit-index-vs-stored-atlas",
        "boundary": (
            "Starts after fixture loading, scalar decoding, U14 point-table preparation, "
            "field and unit constants, and binary-inverse correction setup. Includes scalar "
            "reduction, certified Voronoi selection, signed-word recoding, orbit indexing, "
            "point lookup, grouped-gauge additions, final inversion, affine formatting, "
            "and expected-point verification. Stops after that verification."
        ),
    },
    "formula": {
        "modes": (
            ("reference", "unit_orbit_u256_arithmetic14_fixed", "u256-arithmetic"),
            ("candidate", "unit_orbit_u256_formula14_fixed", "u256-formula"),
        ),
        "retained_bytes": {"reference": 65_188_008, "candidate": 64_314_112},
        "native_tests": 85,
        "algebra": ROOT / "experiments/prime-j0-u14-gauge-20261010/check_algebra.py",
        "comparison_kind": "single-public-scalar-u14-point-only-table-vs-digit-atlas",
        "boundary": (
            "Starts after fixture loading, scalar decoding, U14 point-table preparation, "
            "field and unit constants, and binary-inverse correction setup. Includes scalar "
            "reduction, certified Voronoi selection, signed-word recoding, orbit and digit "
            "computation, point lookup, grouped-gauge additions, final inversion, affine "
            "formatting, and expected-point verification. Stops after that verification."
        ),
    },
}
INDICES = (0, 16, 32, 48, 64, 80, 96, 112, 128)


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def decoded(value):
    return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")


def source_paths(comparison):
    """Bind embedded Rust fixture/atlas files as well as direct sources."""
    paths = set(BASE_SOURCE_PATHS)
    if comparison in ("gauge", "arithmetic", "formula"):
        paths.update(GAUGE_SOURCE_PATHS)
    if comparison in ("arithmetic", "formula"):
        paths.update(ARITHMETIC_SOURCE_PATHS)
    if comparison == "formula":
        paths.update(FORMULA_SOURCE_PATHS)
    pattern = re.compile(r'(?:include_(?:bytes|str)!\(\s*|#\[path\s*=\s*)"([^"]+)"')
    pending = [path for path in paths if path.suffix == ".rs"]
    while pending:
        source = pending.pop()
        for name in pattern.findall(source.read_text()):
            path = (source.parent / name).resolve(strict=True)
            path.relative_to(ROOT)
            if path not in paths:
                paths.add(path)
                if path.suffix == ".rs":
                    pending.append(path)
    return sorted(paths)


def parse_row(line):
    parts = line.split()
    if not parts or any(part.count("=") != 1 for part in parts):
        raise ValueError("malformed output row")
    row = dict(part.split("=", 1) for part in parts)
    if len(row) != len(parts):
        raise ValueError("duplicate output field")
    return row


def expected(case):
    return {
        "curve": "secp256k1", "base_x": case["base_x_hex"],
        "base_y": case["base_y_hex"], "scalar": case["scalar_hex"],
        "point": ("identity" if case["expected_identity"] else
                  case["expected_x_hex"] + ":" + case["expected_y_hex"]),
    }


def verify_row(row, case, mode, *, timed=False):
    fields = expected(case)
    if row.get("verified") != "1" or row.get("mode") != mode:
        raise ValueError("missing verification or wrong mode")
    if any(row.get(key) != value for key, value in fields.items()):
        raise ValueError("fixture input or point mismatch")
    if timed:
        online = float(row["online_ms"])
        preparation = float(row["preparation_ms"])
        if (not math.isfinite(online) or not math.isfinite(preparation) or
                online <= 0 or preparation < 0):
            raise ValueError("invalid timer")


def run_record(argv, out_dir, name, *, timeout=1800):
    try:
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                              timeout=timeout, check=False)
        stdout_text, stderr_text, exit_code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as error:
        stdout_text, stderr_text, exit_code = decoded(error.stdout), decoded(error.stderr), 124
    stdout = out_dir / (name + ".stdout.txt")
    stderr = out_dir / (name + ".stderr.txt")
    exit_file = out_dir / (name + ".exit")
    stdout.write_text(stdout_text)
    stderr.write_text(stderr_text)
    exit_file.write_text(str(exit_code) + "\n")
    return {
        "argv": [str(arg) for arg in argv], "exit_code": exit_code,
        "stdout_file": stdout.name, "stdout_sha256": sha(stdout),
        "stderr_file": stderr.name, "stderr_sha256": sha(stderr),
        "exit_file": exit_file.name, "exit_sha256": sha(exit_file),
    }


def rows_for(record, out_dir, count):
    if record["exit_code"] != 0:
        raise ValueError("command failed: " + " ".join(record["argv"]))
    rows = [parse_row(line) for line in
            (out_dir / record["stdout_file"]).read_text().splitlines() if line.strip()]
    if len(rows) != count:
        raise ValueError(f"expected {count} output rows, found {len(rows)}")
    return rows


def verify(out_dir, comparison):
    if platform.system() != "Linux":
        raise SystemExit("host replay requires Linux and GNU time -v")
    out_dir = out_dir.resolve()
    if out_dir.exists():
        raise SystemExit("output directory already exists")
    out_dir.mkdir(parents=True)
    fixture = json.loads(FIXTURE.read_text())
    if fixture.get("schema") != 1 or len(fixture.get("cases", [])) != 129:
        raise SystemExit("unexpected fixture schema or count")
    config = COMPARISONS[comparison]
    source_sha = {str(path.relative_to(ROOT)): sha(path)
                  for path in source_paths(comparison)}
    cargo = NATIVE / "Cargo.toml"
    target_dir = out_dir / "target"
    env = dict(os.environ, CARGO_TARGET_DIR=str(target_dir))

    def cargo_run(name, args):
        argv = ["cargo", args[0], "--manifest-path", str(cargo), *args[1:]]
        try:
            proc = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=3600, check=False)
            output, exit_code = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as error:
            output, exit_code = decoded(error.stdout) + decoded(error.stderr), 124
        log = out_dir / (name + ".log")
        exit_file = out_dir / (name + ".exit")
        log.write_text(output)
        exit_file.write_text(str(exit_code) + "\n")
        return {"argv": argv, "exit_code": exit_code, "log_file": log.name,
                "log_sha256": sha(log), "exit_file": exit_file.name,
                "exit_sha256": sha(exit_file)}

    algebra = run_record([sys.executable, str(config["algebra"])],
                         out_dir, "algebra-check")
    if algebra["exit_code"] != 0:
        raise SystemExit("field algebra check failed; raw output retained")
    algebra_result = json.loads((out_dir / algebra["stdout_file"]).read_text())
    if (algebra_result.get("status") != "passed" or
            len(algebra_result.get("checks", {})) != 5 or
            not all(algebra_result["checks"].values())):
        raise SystemExit("field algebra identities failed")

    tests = cargo_run("native-tests", ["test", "--locked", "--release",
                                        "--bin", "eisenstein_fixed", "--",
                                        "--test-threads=2"])
    log = (out_dir / tests["log_file"]).read_text()
    match = re.search(r"test result: ok\. (\d+) passed; 0 failed;", log)
    if (tests["exit_code"] != 0 or not match or
            int(match.group(1)) != config["native_tests"]):
        raise SystemExit("native release suite failed; raw log retained in " + str(out_dir))
    build = cargo_run("native-build", ["build", "--locked", "--release",
                                        "--bin", "eisenstein_fixed"])
    if build["exit_code"] != 0:
        raise SystemExit("native release build failed; raw log retained in " + str(out_dir))
    binary = target_dir / "release/eisenstein_fixed"
    records = {}
    fixture_rows = {}
    resources = {}
    for label, mode, flag in config["modes"]:
        record = run_record([str(binary), f"--check-scalar-unit-orbit-{flag}-fixed-fixture",
                             str(FIXTURE)], out_dir, label + "-fixture")
        rows = rows_for(record, out_dir, 129)
        for index, row in enumerate(rows):
            verify_row(row, fixture["cases"][index], mode)
        records[label] = record
        fixture_rows[label] = rows
        resource = run_record(["/usr/bin/time", "-v", str(binary),
                               f"--benchmark-scalar-unit-orbit-{flag}-fixed-case",
                               str(FIXTURE), "0"], out_dir, label + "-resource")
        row = rows_for(resource, out_dir, 1)[0]
        verify_row(row, fixture["cases"][0], mode, timed=True)
        if int(row["retained_bytes"]) != config["retained_bytes"][label]:
            raise ValueError("retained table byte count changed")
        stderr = (out_dir / resource["stderr_file"]).read_text()
        matches = re.findall(r"^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$",
                             stderr, flags=re.MULTILINE)
        if len(matches) != 1:
            raise ValueError("GNU time did not report one maximum RSS value")
        resource["max_rss_kib"] = int(matches[0])
        resource["retained_bytes"] = int(row["retained_bytes"])
        resources[label] = resource
    for left, right in zip(fixture_rows["reference"], fixture_rows["candidate"]):
        if {k: v for k, v in left.items() if k != "mode"} != {
                k: v for k, v in right.items() if k != "mode"}:
            raise ValueError("paired fixture rows differ")
    receipt = {
        "schema": 1, "status": "passed", "comparison": comparison,
        "modes": {label: mode for label, mode, _ in config["modes"]},
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "rustc_version": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "cargo_version": subprocess.check_output(["cargo", "--version"], text=True).strip(),
        "binary": str(binary), "binary_sha256": sha(binary),
        "source_sha256": source_sha,
        "native_tests_passed": config["native_tests"],
        "algebra": algebra, "tests": tests, "build": build,
        "runs": records, "resources": resources,
        "fixture_cases_per_mode": 129, "cpu_speedup_claim": None,
        "isolation_receipt": None,
    }
    receipt_path = out_dir / "verification.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"receipt": str(receipt_path), "binary_sha256": sha(binary),
                      "status": "passed"}, sort_keys=True))


def manifest(args):
    receipt_path = args.receipt.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text())
    comparison = receipt.get("comparison")
    if comparison not in COMPARISONS:
        raise SystemExit("unknown comparison in host receipt")
    config = COMPARISONS[comparison]
    if (receipt.get("status") != "passed" or
            receipt.get("native_tests_passed") != config["native_tests"] or
            receipt.get("modes") != {label: mode for label, mode, _ in config["modes"]}):
        raise SystemExit("host verification did not pass")
    if (set(receipt.get("runs", {})) != {"reference", "candidate"} or
            set(receipt.get("resources", {})) != {"reference", "candidate"}):
        raise SystemExit("host verification arms differ")
    if set(receipt.get("source_sha256", {})) != {
            str(path.relative_to(ROOT)) for path in source_paths(comparison)}:
        raise SystemExit("host verification source set differs")
    if (receipt.get("fixture_cases_per_mode") != 129 or
            any(record["exit_code"] != 0 for record in
                (receipt["algebra"], receipt["tests"], receipt["build"],
                 *receipt["runs"].values(), *receipt["resources"].values()))):
        raise SystemExit("host verification run failed")
    binary = Path(receipt["binary"]).resolve(strict=True)
    if sha(binary) != receipt["binary_sha256"]:
        raise SystemExit("verified binary differs")
    artifacts = [binary, receipt_path]
    for name, digest in receipt["source_sha256"].items():
        path = ROOT / name
        if sha(path) != digest:
            raise SystemExit("verified source differs: " + name)
        artifacts.append(path)
    for record in (receipt["algebra"], receipt["tests"], receipt["build"],
                   *receipt["runs"].values(), *receipt["resources"].values()):
        for stream in ("log", "stdout", "stderr", "exit"):
            if stream + "_file" not in record:
                continue
            path = receipt_path.parent / record[stream + "_file"]
            if sha(path) != record[stream + "_sha256"]:
                raise SystemExit("raw host output differs: " + str(path))
            artifacts.append(path)
    fixture = json.loads(FIXTURE.read_text())
    cases = []
    flags = {label: flag for label, _, flag in config["modes"]}
    for index in INDICES:
        case = fixture["cases"][index]
        if case["index"] != index:
            raise SystemExit("fixture order differs")
        fields = expected(case)
        common = [str(FIXTURE), str(index)]
        cases.append({
            "id": f"scalar-{index}",
            "expected_fields": {key: fields[key] for key in
                                ("curve", "base_x", "base_y", "scalar")},
            "expected_result": fields["point"],
            "reference": [str(binary),
                          f"--benchmark-scalar-unit-orbit-{flags['reference']}-fixed-case",
                          *common],
            "candidate": [str(binary),
                          f"--benchmark-scalar-unit-orbit-{flags['candidate']}-fixed-case",
                          *common],
        })
    result = {
        "schema": 1, "workdir": str(ROOT),
        "isolation": {"cgroup": args.cgroup, "cpus": args.cpus,
                      "execution_cpu": args.execution_cpu, "mem_nodes": args.mem_node},
        "artifacts": [str(path) for path in dict.fromkeys(artifacts)],
        "timeout_s": 1200, "repetitions": args.repetitions,
        "metric_field": "online_ms", "measurement_boundary": config["boundary"],
        "pair_fields": ["curve", "base_x", "base_y", "scalar"],
        "result_field": "point", "workload_sha256": sha(FIXTURE),
        "comparison_kind": config["comparison_kind"],
        "cases": cases,
    }
    sys.path.insert(0, str(ROOT / "scripts"))
    from isolated_bench import require_manifest
    require_manifest(result)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("manifest already exists")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases), "repetitions": args.repetitions,
                      "manifest_sha256": sha(output)}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--output-dir", type=Path, required=True)
    verify_parser.add_argument("--comparison", choices=COMPARISONS, default="point")
    manifest_parser = commands.add_parser("manifest")
    manifest_parser.add_argument("--receipt", type=Path, required=True)
    manifest_parser.add_argument("--cgroup", required=True)
    manifest_parser.add_argument("--cpus", required=True)
    manifest_parser.add_argument("--execution-cpu", type=int, required=True)
    manifest_parser.add_argument("--mem-node", required=True)
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.output_dir, args.comparison)
    else:
        manifest(args)


if __name__ == "__main__":
    main()
