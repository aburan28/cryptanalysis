"""Frozen public query with a rank-aware quartic multiplication kernel."""

import argparse
import importlib.util
from pathlib import Path

import circuit as method

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HORNER = ROOT / "n41_single_branch_horner_20261011"

spec = importlib.util.spec_from_file_location("frozen_n41_horner_runner", HORNER / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

base.HERE = HERE
base.method = method
original_profile = base.profile


def profile(circuit, meta, construction_seconds):
    result = original_profile(circuit, meta, construction_seconds)
    for key in ("quartic_sparse_multiplications", "quartic_generic_multiplications",
                "quartic_sparse_pair_products", "quartic_and_gates"):
        result[key] = meta[key]
    return result


def sources():
    return {"basis_aware_run.py": Path(__file__),
            "basis_aware_circuit.py": HERE / "circuit.py",
            "basis_aware_sparse.py": HERE / "sparse.py",
            "horner_run.py": HORNER / "run.py",
            "horner_circuit.py": HORNER / "circuit.py",
            "norm_result.json": base.NORM,
            "heldout_input.txt": base.SOURCE_INPUT,
            "corrected_lifts.json": base.PUBLIC_LIFTS,
            "known_blocks.json": base.KNOWN_BLOCKS,
            "known_branch_audit.json": base.KNOWN_BRANCHES,
            "karatsuba_circuit.py": ROOT.parent / "koblitz-polynomial-w-pair-20260925" / "karatsuba_circuit.py",
            "circuit_sat.py": ROOT.parent / "koblitz-s5-invariant-20260924" / "circuit_sat.py",
            "cryptominisat5": base.SOLVER}


base.profile = profile
base.sources = sources


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "control", "query"))
    mode = parser.parse_args().mode
    {"freeze": base.freeze, "control": base.control, "query": base.query}[mode]()
