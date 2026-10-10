#!/usr/bin/env python3
"""Check sign-unit XCNF construction and independent clause/XOR audit."""

from pathlib import Path
import tempfile

from run_sign_enum import make_variant, verify_xcnf


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sign-enum-codec-") as directory:
        path = Path(directory) / "branch.xcnf"
        base = b"1 0\nx -2 1 0\n"
        make_variant(base, 2, 2, [2], 1, path)
        assert path.read_text() == "p cnf 2 3\n1 0\nx -2 1 0\n2 0\n"
        assert verify_xcnf(path, {1: True, 2: True})
        assert not verify_xcnf(path, {1: True, 2: False})
        make_variant(base, 2, 2, [2], 0, path)
        assert path.read_text().endswith("-2 0\n")
        assert not verify_xcnf(path, {1: True, 2: True})
    print("PASS: sign variants preserve XCNF rows and audit CNF/XOR/unit semantics")


if __name__ == "__main__":
    main()
