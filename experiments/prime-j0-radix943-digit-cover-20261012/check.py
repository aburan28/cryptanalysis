#!/usr/bin/env python3
"""Build the digit-cover theorems and replay the four-corner chooser."""

from hashlib import sha256
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PRIOR = "experiments/prime-j0-radix943-termination-20261012/Termination.lean"
MODULE = "experiments/prime-j0-radix943-digit-cover-20261012/DigitCover.lean"
TOOLCHAIN = "leanprover/lean4:v4.34.1"
REQUIRED = (
    "nearest_step_equation",
    "nearest_digit_bound",
    "recode_length",
    "recode_digit_bounds",
    "recode_steps",
    "nearest_thirteen_terminate",
    "basis_determinant",
    "basis_norms",
    "nearest_representative_bound",
    "scalar_recode_terminates",
    "basis_kernel",
    "nearest_representative_congruence",
    "scalar_recode_reconstruct",
    "scalar_recode_congruence",
)
FILES = (
    "experiments/prime-j0-radix943-digit-cover-20261012/check.py",
    MODULE,
    "experiments/prime-j0-radix943-digit-cover-20261012/lean-toolchain",
    "experiments/prime-j0-radix943-digit-cover-20261012/PROOF.md",
    "experiments/prime-j0-radix943-digit-cover-20261012/RESULT.md",
    "experiments/prime-j0-radix943-digit-cover-20261012/lean-build.txt",
    "experiments/prime-j0-radix943-digit-cover-20261012/fixtures.json",
    "experiments/prime-j0-radix943-digit-cover-20261012/scalar-fixtures.json",
    PRIOR,
    "experiments/prime-j0-secp256k1-native/radix943_screen.py",
    "experiments/prime-j0-secp256k1-native/src/bin/eisenstein_fixed/unit_orbit_windows.rs",
)


def digest(path):
    return sha256((ROOT / path).read_bytes()).hexdigest()


def run_lean(args, env, stdin=None):
    result = subprocess.run(
        ["lean", *args], input=stdin, text=True, capture_output=True,
        cwd=ROOT, env=env, timeout=180,
    )
    if result.returncode:
        raise RuntimeError(f"lean {' '.join(args)} failed:\n{result.stdout}{result.stderr}")
    return result.stdout + result.stderr


def cases():
    radix = 943
    boundaries = (
        (0, 0), (1, 2), (-1, -2), (radix, radix),
        (radix - 1, 1), (radix, -radix),
        (-radix, radix), (-radix - 1, radix + 1),
        (radix // 2, radix // 2),
        (2 * radix - 1, -2 * radix + 1),
    )
    rng = random.Random(20261012)
    return list(boundaries) + [
        (rng.randrange(-(1 << 130), 1 << 130),
         rng.randrange(-(1 << 130), 1 << 130))
        for _ in range(32)
    ]


def scalar_cases(order):
    rng = random.Random(2026101213)
    return [0, 1, 2, order - 2, order - 1] + [
        rng.randrange(order) for _ in range(7)
    ]


def build():
    assert (HERE / "lean-toolchain").read_text().strip() == TOOLCHAIN
    assert not re.search(r"\b(sorry|admit|sorryAx)\b", (ROOT / MODULE).read_text())
    env = dict(os.environ, ELAN_TOOLCHAIN=TOOLCHAIN)
    with tempfile.TemporaryDirectory(prefix="prime-j0-digit-cover-") as temp:
        env["LEAN_PATH"] = temp
        old_output = run_lean(["-o", str(Path(temp) / "Termination.olean"), PRIOR], env)
        new_output = run_lean(["-o", str(Path(temp) / "DigitCover.olean"), MODULE], env)
        for name in REQUIRED:
            assert f"'PrimeJ0Radix943DigitCover.{name}'" in new_output, name
        allowed_axioms = {"propext", "Classical.choice", "Quot.sound"}
        for line in (old_output + new_output).splitlines():
            if " depends on axioms: " in line:
                reported = set(line.split("[", 1)[1].split("]", 1)[0].split(", "))
                assert reported <= allowed_axioms, line
        assert "sorryAx" not in old_output + new_output

        source = ROOT / "experiments/prime-j0-secp256k1-native"
        sys.path.insert(0, str(source))
        import radix943_screen as reference

        samples = cases()
        statements = ["import DigitCover", "open PrimeJ0Radix943DigitCover"]
        for a, b in samples:
            pair = f"(({a} : Int), ({b} : Int))"
            statements += [f"#eval (nearestStep {pair}).1",
                           f"#eval (nearestStep {pair}).2"]
        replay = run_lean(["--stdin"], env, "\n".join(statements) + "\n")
        lines = replay.splitlines()
        assert len(lines) == 2 * len(samples), (len(lines), replay[:500])
        pattern = re.compile(r"\((-?\d+), (-?\d+)\)")
        records = []
        for index, (a, b) in enumerate(samples):
            digit_match = pattern.fullmatch(lines[2 * index])
            quotient_match = pattern.fullmatch(lines[2 * index + 1])
            assert digit_match and quotient_match, lines[2 * index:2 * index + 2]
            digit = tuple(map(int, digit_match.groups()))
            quotient = tuple(map(int, quotient_match.groups()))
            expected = reference.nearest_digit((a, b))
            assert digit == expected, ((a, b), digit, expected)
            assert a == digit[0] + 943 * quotient[0]
            assert b == digit[1] + 943 * quotient[1]
            assert 3 * reference.norm(digit) <= 943**2
            records.append({"input": [a, b], "digit": list(digit),
                            "quotient": list(quotient)})

        scalars = scalar_cases(reference.ORDER)
        scalar_statements = ["import DigitCover", "open PrimeJ0Radix943DigitCover"]
        for scalar in scalars:
            source_expr = f"({scalar} : Int)"
            scalar_statements += [
                f"#eval nearestRepresentative {source_expr}",
                "#eval String.intercalate \";\" "
                f"(((recode 13 (nearestRepresentative {source_expr})).1).map "
                "fun d => toString d.1 ++ \",\" ++ toString d.2)",
            ]
        scalar_replay = run_lean(
            ["--stdin"], env, "\n".join(scalar_statements) + "\n"
        )
        scalar_lines = scalar_replay.splitlines()
        assert len(scalar_lines) == 2 * len(scalars), (len(scalar_lines), scalar_replay[:500])
        scalar_records = []
        for index, scalar in enumerate(scalars):
            rep_match = pattern.fullmatch(scalar_lines[2 * index])
            encoded_digits = json.loads(scalar_lines[2 * index + 1])
            digit_matches = [item.split(",") for item in encoded_digits.split(";")]
            assert rep_match and len(digit_matches) == 13, scalar_lines[2 * index:2 * index + 2]
            rep = tuple(map(int, rep_match.groups()))
            digits = [tuple(map(int, pair)) for pair in digit_matches]
            expected_rep, expected_digits = reference.recode(scalar)
            assert rep == expected_rep, (scalar, rep, expected_rep)
            assert digits == expected_digits, (scalar, digits, expected_digits)
            scalar_records.append({"scalar_hex": hex(scalar),
                                   "representative": list(rep),
                                   "digits": [list(pair) for pair in digits]})

    (HERE / "fixtures.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    (HERE / "scalar-fixtures.json").write_text(
        json.dumps(scalar_records, indent=2, sort_keys=True) + "\n"
    )
    (HERE / "lean-build.txt").write_text(
        f"toolchain={TOOLCHAIN}\n"
        f"$ lean -o $LEAN_PATH/Termination.olean {PRIOR}\n{old_output}exit_code=0\n"
        f"$ lean -o $LEAN_PATH/DigitCover.olean {MODULE}\n{new_output}exit_code=0\n"
        f"$ lean --stdin < {len(samples)} frozen chooser fixtures\n"
        f"matched_python_digits={len(samples)}\n"
        f"checked_quotient_equations={len(samples)}\nexit_code=0\n"
        f"$ lean --stdin < {len(scalars)} frozen scalar recodings\n"
        f"matched_python_scalar_recodings={len(scalars)}\nexit_code=0\n"
    )
    print(f"Lean theorems checked; {len(samples)} digit and {len(scalars)} scalar fixtures matched Python")


def receipt():
    return {
        "schema": 1,
        "status": "lean_digit_cover_checked",
        "toolchain": TOOLCHAIN,
        "radix": 943,
        "windows": 13,
        "chooser_fixture_count": len(cases()),
        "scalar_fixture_count": 12,
        "sha256": {path: digest(path) for path in FILES},
    }


def main():
    if "--proof" in sys.argv:
        build()
    else:
        raw = (json.dumps(receipt(), indent=2, sort_keys=True) + "\n").encode()
        path = HERE / "receipt.json"
        if "--check" in sys.argv:
            assert path.read_bytes() == raw
        else:
            path.write_bytes(raw)
        print(f"receipt_sha256={sha256(raw).hexdigest()}")


if __name__ == "__main__":
    main()
