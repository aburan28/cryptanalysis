#!/usr/bin/env python3
"""Exhaust the seven-input Boolean truth table through CryptoMiniSat."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from circuit import Circuit
from weight34 import require_weight_three_or_four


CMS = Path("/opt/homebrew/bin/cryptominisat5")


def main(tmp_dir: Path) -> None:
    assert CMS.is_file()
    with TemporaryDirectory(dir=tmp_dir) as directory:
        instance = Path(directory) / "weight34.xcnf"
        for mask in range(1 << 7):
            circuit = Circuit(7, [0, 1])
            variables = [circuit.variable() for _ in range(7)]
            require_weight_three_or_four(circuit, variables)
            for bit, variable in enumerate(variables):
                circuit.clauses.append(
                    f"{variable if mask & (1 << bit) else -variable} 0"
                )
            circuit.write(instance)
            result = subprocess.run(
                [str(CMS), "--verb=0", "--threads=1", str(instance)],
                capture_output=True, text=True, timeout=10, check=False,
            )
            observed = "s SATISFIABLE" in result.stdout
            unsat = "s UNSATISFIABLE" in result.stdout
            assert observed != unsat, (mask, result.returncode, result.stdout, result.stderr)
            assert observed == (mask.bit_count() in (3, 4)), mask
    print("weight-three-or-four XCNF truth table: 128/128 PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tmp_dir", type=Path)
    main(parser.parse_args().tmp_dir)
