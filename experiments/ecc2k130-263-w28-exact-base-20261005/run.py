#!/usr/bin/env sage -python
"""Build and run the frozen bit-packed exact W_d census through checked Sage."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"
PARENT = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/analysis.json"
CONFIG = HERE / "CONFIG.json"
RUNTIME = HERE / "runtime-info.json"
SOURCE = HERE / "enumerate.cpp"
VERIFIER = HERE / "verify_sage.py"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def encode(value):
    return sum(int(bit) << i for i, bit in enumerate(value.polynomial().list()))


def field_and_alpha(route, config):
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**131, "t", modulus=t**131 + t**13 + t**2 + t + 1)

    def decode(word):
        word = int(word)
        return field(sum(t**i for i in range(word.bit_length()) if (word >> i) & 1))

    a4, a6 = [decode(v) for v in route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"][3:]]
    b = a6 + a4**2
    alpha = b ** (1 << 129)
    assert alpha**4 == b
    assert encode(alpha) == int(config["normalized_descendant_alpha"])
    assert encode(alpha).bit_length() - 1 == config[
        "normalized_descendant_alpha_polynomial_degree"]
    assert int(alpha.trace()) == 1 and int(field.one().trace()) == 1
    assert route["route_id"] == config["curve_route_id"]
    assert route["curve_nodes"]["source"]["curve_id"] == config["source_curve_id"]
    assert route["curve_nodes"]["target"]["curve_id"] == config["target_curve_id"]
    assert route["curve_nodes"]["source"]["cofactor"] == 4
    assert route["curve_nodes"]["target"]["cofactor"] == 4
    normalized = EllipticCurve(field, [1, 0, 0, 0, b])
    torsion = normalized([alpha, alpha**2])
    assert not torsion.is_zero() and not (2 * torsion).is_zero()
    assert (4 * torsion).is_zero()
    return encode(alpha), encode(b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--dimension", type=int, default=28)
    parser.add_argument("--batch-size", type=int, default=2048)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if not 1 <= args.dimension <= config["dimension"]:
        parser.error("dimension must be in 1..28")
    if not 1 <= args.batch_size <= 65536:
        parser.error("batch size must be in 1..65536")
    if args.dimension == config["dimension"] and args.batch_size not in config[
            "repetitions_batch_sizes"]:
        parser.error("full-width batch size must be pre-registered")
    if args.out_dir.exists():
        parser.error("output directory already exists")
    args.out_dir.mkdir(parents=True)
    try:
        assert sha(ROUTE) == config["route_manifest_sha256"]
        assert sha(PARENT) == config["parent_w24_analysis_sha256"]
        assert RUNTIME.is_file() and SOURCE.is_file() and VERIFIER.is_file()
        route = json.loads(ROUTE.read_text())
        alpha, b = field_and_alpha(route, config)
        limbs = [alpha & ((1 << 64) - 1),
                 (alpha >> 64) & ((1 << 64) - 1), alpha >> 128]
        binary = args.out_dir / "enumerate"
        build = ["clang++", "-O3", "-std=c++17", "-Wall", "-Wextra",
                 "-Wconversion", "-Werror", str(SOURCE), "-o", str(binary)]
        with (args.out_dir / "build.stdout").open("wb") as stdout, (
                args.out_dir / "build.stderr").open("wb") as stderr:
            completed = subprocess.run(build, stdout=stdout, stderr=stderr, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"native build failed: {completed.returncode}")
        membership = args.out_dir / "membership.bin"
        native = args.out_dir / "native.json"
        command = [str(binary), str(args.dimension), *map(str, limbs),
                   str(args.batch_size), str(config["max_wall_seconds_per_full_run"]),
                   str(config["max_peak_rss_bytes"]), str(membership), str(native)]
        with (args.out_dir / "run.stdout").open("wb") as stdout, (
                args.out_dir / "run.stderr").open("wb") as stderr:
            completed = subprocess.run(command, stdout=stdout, stderr=stderr,
                                       check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"native census failed: {completed.returncode}")
        raw = json.loads(native.read_text())
        assert raw["status"] == "completed"
        assert raw["kind"] == "ecc2k130_degree263_exact_w28_packed_base_census"
        assert raw["membership_encoding"] == config["membership_encoding"]
        assert raw["dimension"] == args.dimension
        assert raw["batch_size"] == args.batch_size
        assert raw["checked_nonzero_masks"] == (1 << args.dimension) - 1
        assert raw["alpha_limbs"] == limbs
        assert sum(part << (64 * i) for i, part in enumerate(raw["normalized_b_limbs"])) == b
        for curve in ("source", "descendant"):
            row = raw[curve]
            assert row["actual_usable_points_B"] == 2 * row["sign_folded_columns"]
            assert row["sign_folded_columns"] == row["rational_w"]
            assert row["two_element_reciprocal_pairs"] == 0
        paired = raw["paired_rationality"]
        assert sum(paired.values()) == (1 << args.dimension) - 1
        assert paired["both"] + paired["source_only"] == raw["source"]["rational_w"]
        assert paired["both"] + paired["descendant_only"] == raw[
            "descendant"]["rational_w"]
        assert membership.stat().st_size == ((1 << args.dimension) + 2) // 4
        if args.dimension == config["dimension"]:
            assert membership.stat().st_size == config["raw_membership_bytes"]
        with membership.open("rb") as stream:
            stream.seek(-1, 2)
            last = stream.read(1)[0]
        assert (last >> (2 * (((1 << args.dimension) - 1) % 4))) == 0
        compiler = subprocess.run(["clang++", "--version"], check=True,
                                  capture_output=True, text=True).stdout.splitlines()[0]
        artifacts = {p.name: sha(p) for p in (
            binary, membership, native,
            args.out_dir / "build.stdout", args.out_dir / "build.stderr",
            args.out_dir / "run.stdout", args.out_dir / "run.stderr")}
        result = {
            "schema": "ecc2k130-263-exact-w-base-run-v1",
            "status": "completed_unverified",
            "candidate_id": None,
            "dimension": args.dimension,
            "batch_size": args.batch_size,
            "curve_route_id": route["route_id"],
            "source_curve_id": config["source_curve_id"],
            "target_curve_id": config["target_curve_id"],
            "normalized_descendant_alpha": str(alpha),
            "normalized_descendant_b": str(b),
            "source": raw["source"],
            "descendant": raw["descendant"],
            "paired_rationality": paired,
            "elapsed_ns": raw["elapsed_ns"],
            "peak_rss_bytes": raw["peak_rss_bytes"],
            "field_backend": raw["field_backend"],
            "compiler": compiler,
            "build_argv": build,
            "run_argv": command,
            "inputs_sha256": {str(p.relative_to(ROOT)): sha(p)
                              for p in (CONFIG, ROUTE, PARENT, RUNTIME, SOURCE,
                                        Path(__file__), VERIFIER)},
            "artifacts_sha256": artifacts,
            "natural_pdp_yield": None,
            "verified_relation_rank": None,
            "verified_logarithm": None,
            "online_wall_time": None,
            "rho_ratio": None,
        }
        (args.out_dir / "summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"out_dir": str(args.out_dir), "source_B":
                          raw["source"]["actual_usable_points_B"],
                          "descendant_B": raw["descendant"]["actual_usable_points_B"]}))
    except Exception as error:
        failure = {"status": "failed", "error": repr(error),
                   "input_sha256": {str(p.relative_to(ROOT)): sha(p)
                                    for p in (CONFIG, ROUTE, PARENT, RUNTIME, SOURCE,
                                              Path(__file__), VERIFIER)
                                    if p.is_file()}}
        (args.out_dir / "failure.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n")
        raise


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("optimized Python disables required assertions")
    main()
