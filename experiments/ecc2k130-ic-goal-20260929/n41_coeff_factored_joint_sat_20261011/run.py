"""Run the factored coefficient variant on the same frozen N41 public point."""

import argparse
import importlib.util
from pathlib import Path

import circuit as method

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "n41_single_branch_joint_sat_20261011"

spec = importlib.util.spec_from_file_location("n41_single_branch_baseline_runner", OLD / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.HERE = HERE
base.method = method


def sources():
    return {"factored_run.py": Path(__file__),
            "factored_circuit.py": HERE / "circuit.py",
            "baseline_run.py": OLD / "run.py",
            "baseline_circuit.py": OLD / "circuit.py",
            "coefficient_result.json": OLD / "coefficient_result.json",
            "norm_result.json": base.NORM,
            "heldout_input.txt": base.SOURCE_INPUT,
            "corrected_lifts.json": base.PUBLIC_LIFTS,
            "known_blocks.json": base.KNOWN_BLOCKS,
            "known_branch_audit.json": base.KNOWN_BRANCHES,
            "karatsuba_circuit.py": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat.py": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py",
            "cryptominisat5": base.SOLVER}


base.sources = sources


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": base.freeze, "control": base.control, "query": base.query}[mode]()
