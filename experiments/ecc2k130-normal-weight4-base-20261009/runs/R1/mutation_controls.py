#!/usr/bin/env python3
"""Replay two frozen Q1421 source/decision corruptions against the Sage verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


RUN = Path(__file__).resolve().parent
HERE = RUN.parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from census import cyclic_gap_representatives, inverse_mod, transform  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_verifier(script: Path, result: Path, runtime: Path, output: Path) -> dict:
    argv = [
        "/Volumes/SSD990/cryptanalysis/sage", "-python", str(script),
        "--result", str(result), "--runtime-info", str(runtime),
        "--out", str(output),
    ]
    started = time.perf_counter()
    process = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    return {
        "exit_code": process.returncode,
        "wall_seconds": time.perf_counter() - started,
        "stderr_tail": process.stderr[-800:],
        "unexpected_output_created": output.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("refusing to overwrite a mutation receipt")

    config_path = HERE / "CONFIG.json"
    result_path = RUN / "producer.json"
    runtime_path = RUN / "sage_runtime.json"
    verifier_path = HERE / "verify_sage.py"
    config = json.loads(config_path.read_text())
    result = json.loads(result_path.read_text())
    parent_path = ROOT / config["parent_normal_basis"]["path"]
    parent = json.loads(parent_path.read_text())

    with tempfile.TemporaryDirectory(prefix="ecc2k130-weight4-mutations-") as tmp:
        temporary = Path(tmp)
        source_dir = temporary / "experiments" / HERE.name
        source_dir.mkdir(parents=True)
        copied_verifier = source_dir / "verify_sage.py"
        shutil.copyfile(verifier_path, copied_verifier)
        shutil.copyfile(config_path, source_dir / "CONFIG.json")
        copied_parent = temporary / config["parent_normal_basis"]["path"]
        copied_parent.parent.mkdir(parents=True)
        parent["normal_orbit_polynomial_words"][0] = str(
            int(parent["normal_orbit_polynomial_words"][0]) ^ 1
        )
        copied_parent.write_text(json.dumps(parent, indent=2, sort_keys=True) + "\n")
        parent_run = run_verifier(
            copied_verifier, result_path, runtime_path,
            temporary / "parent_output.json",
        )

        degree = config["field"]["degree"]
        modulus = sum(1 << exponent for exponent in config["field"]["modulus_exponents"])
        original_parent = json.loads(parent_path.read_text())
        basis = [int(word) for word in original_parent["normal_orbit_polynomial_words"]]
        to_normal = [int(word) for word in original_parent["polynomial_to_normal_columns"]]
        flags = bytearray()
        for _, mask in cyclic_gap_representatives(degree):
            word = transform(mask, basis)
            inverse = inverse_mod(word, modulus, degree)
            coordinates = transform(inverse, to_normal)
            flags.append(
                int(coordinates.bit_count() % 2 == 0)
                | (int(coordinates.bit_count() == 4) << 1)
            )
        original_flags_digest = hashlib.sha256(flags).hexdigest()
        if original_flags_digest != result["rationality_and_reciprocal_flags_sha256"]:
            raise ArithmeticError("reconstructed decision stream differs from producer")
        original_first_flag = flags[0]
        flags[0] ^= 1  # Change exactly one rationality decision bit.
        modified_flags_digest = hashlib.sha256(flags).hexdigest()
        modified_result = dict(result)
        modified_result["rationality_and_reciprocal_flags_sha256"] = modified_flags_digest
        modified_result_path = temporary / "flipped_rationality.json"
        modified_result_path.write_text(
            json.dumps(modified_result, indent=2, sort_keys=True) + "\n"
        )
        rationality_run = run_verifier(
            verifier_path, modified_result_path, runtime_path,
            temporary / "rationality_output.json",
        )

    parent_rejected = (
        parent_run["exit_code"] != 0
        and "source, result, or checked runtime identity mismatch"
        in parent_run["stderr_tail"]
        and not parent_run["unexpected_output_created"]
    )
    rationality_rejected = (
        rationality_run["exit_code"] != 0
        and "producer mismatch: rationality_and_reciprocal_flags_sha256"
        in rationality_run["stderr_tail"]
        and not rationality_run["unexpected_output_created"]
    )
    receipt = {
        "schema": "ecc2k130-normal-weight4-mutation-controls-v1",
        "status": "PASS_MUTATION_CONTROLS" if parent_rejected and rationality_rejected
                  else "FAIL_MUTATION_CONTROLS",
        "normal_basis_word_mutation": {
            "index": 0, "xor_polynomial_bit": 0, "rejected": parent_rejected,
            **parent_run,
        },
        "rationality_bit_mutation": {
            "orbit_index": 0,
            "original_flag_byte": original_first_flag,
            "mutated_flag_byte": flags[0],
            "original_flags_sha256": original_flags_digest,
            "mutated_flags_sha256": modified_flags_digest,
            "rejected": rationality_rejected,
            **rationality_run,
        },
        "config_sha256": sha256(config_path),
        "producer_result_sha256": sha256(result_path),
        "runtime_info_sha256": sha256(runtime_path),
        "verifier_sha256": sha256(verifier_path),
        "mutation_script_sha256": sha256(Path(__file__)),
    }
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(receipt["status"])
    if receipt["status"] != "PASS_MUTATION_CONTROLS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
