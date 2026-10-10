#!/usr/bin/env python3
"""Build a full projective-S3 XCNF with an archived cancellation target."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import resource
import sys
import time


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-projective-s3-20261010"
sys.path.insert(0, str(PARENT))
import build_projective as parent  # noqa: E402


ref = parent.ref
finite = parent.finite


def peak_bytes():
    size = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return size if sys.platform == "darwin" else size * 1024


def encode_with_map(policy, prog, roots, leaves, xs):
    """Mirror the frozen encoder, returning its named input literals."""
    config = ref.read(PARENT / "CONFIG.json")
    formula = finite.cnf.Cnf()
    literals = {("one", 0): formula.true}
    selectors = []
    cutoff = config[policy + "_last_selected_mask"]
    for index, leaf in enumerate(leaves):
        bits = [formula.newVar() for _ in leaf["selectors"]]
        selectors.append(bits)
        for bit, literal in enumerate(bits):
            literals[("s%d" % index, bit)] = literal
        for name in ("x", "z"):
            for bit in range(ref.DEGREE):
                literals[("%s%d" % (name, index), bit)] = formula.newVar()
        if cutoff < (1 << 24) - 1:
            upper = [formula.true if cutoff & (1 << bit) else formula.false
                     for bit in range(23, -1, -1)]
            formula.lexLeq(list(reversed(bits)), upper)
    for index in range(5):
        formula.lexLeq(list(reversed(selectors[index])),
                       list(reversed(selectors[index + 1])))
    target_bits, choice = finite.target_mux(formula, xs)
    for bit, literal in enumerate(target_bits):
        literals[("target", bit)] = literal
    for index in range(4):
        for bit in range(ref.DEGREE):
            literals[("t%d" % index, bit)] = formula.newVar()
        literals[("f", index)] = formula.newVar()
    for literal in prog.emitCnf(roots, literals, formula):
        formula.assertZero(literal)
    return formula, choice, literals


def check_parent(policy, config):
    pins = {
        PARENT / "CONFIG.json": "parent_config_sha256",
        PARENT / "build_projective.py": "parent_builder_sha256",
        PARENT / "audit.py": "parent_auditor_sha256",
        PARENT / "runs/R1/audit.json": "parent_audit_receipt_sha256",
        PARENT / "runs/R1/exceptional_group.json":
            "parent_exceptional_group_sha256",
        PARENT / "runs/R1" / (policy + "_projective.xcnf.gz"):
            policy + "_parent_xcnf_gzip_sha256",
    }
    if any(ref.sha(path) != config[key] for path, key in pins.items()):
        raise ValueError("frozen parent source or input digest changed")
    audit = ref.read(PARENT / "runs/R1/audit.json")
    if audit["status"] != "PASS_PROJECTIVE_FORMULAS_AND_BOUNDED_SOLVER_TRANSCRIPTS":
        raise ValueError("parent projective audit did not pass")
    parent.check_inputs(policy)
    witness = ref.read(PARENT / "runs/R1/exceptional_group.json")["policies"][policy]
    if (not witness["first_pair_is_infinity"]
            or not witness["independent_group_law_matches_sage"]):
        raise ValueError("N131 cancellation witness is unverified")
    return witness, audit["policies"][policy]["formula"]["raw_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=parent.POLICIES, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    map_path = args.out.with_suffix(".inputs.json")
    receipt_path = args.out.with_suffix(".json")
    if any(path.exists() for path in (args.out, map_path, receipt_path)):
        parser.error("refusing to overwrite control formula evidence")
    started = time.perf_counter()
    config = ref.read(HERE / "CONFIG.json")
    witness, parent_sha = check_parent(args.policy, config)
    prog, roots, leaves, _ = parent.build_ir(args.policy)
    baseline, _, _ = encode_with_map(
        args.policy, prog, roots, leaves, finite.target_lifts(args.policy))
    baseline_path = args.out.with_suffix(".baseline_check.xcnf")
    if baseline_path.exists():
        parser.error("refusing to overwrite parent identity check")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    baseline.writeDimacs(baseline_path)
    baseline_sha = ref.sha(baseline_path)
    if baseline_sha != parent_sha:
        raise ValueError("copied encoder did not reproduce parent formula")
    baseline_path.unlink()
    del baseline
    gc.collect()
    witness_x = witness["target_x"]
    xs = [witness_x] + [witness_x ^ 1] * 3
    formula, choice, literals = encode_with_map(
        args.policy, prog, roots, leaves, xs)
    formula.writeDimacs(args.out)
    input_vars = {"%s:%d" % key: value for key, value in literals.items()}
    map_path.write_text(json.dumps(input_vars, sort_keys=True,
                                   separators=(",", ":")) + "\n")
    receipt = {
        "schema": "ecc2k130-263-projective-s3-sat-base-v1",
        "status": "CONTROL_FORMULA_BUILT",
        "policy": args.policy,
        "candidate_id": None,
        "proposal_id": config["proposal_id"],
        "parent_formula_sha256": parent_sha,
        "reproduced_parent_formula_sha256": baseline_sha,
        "control_target_x_choices": [str(x) for x in xs],
        "target_selector_variables": choice,
        "input_vars_sha256": ref.sha(map_path),
        "input_vars_count": len(input_vars),
        "formula_sha256": ref.sha(args.out),
        "formula_bytes": args.out.stat().st_size,
        "stats": formula.stats(),
        "config_sha256": ref.sha(HERE / "CONFIG.json"),
        "parent_builder_sha256": ref.sha(PARENT / "build_projective.py"),
        "parent_exceptional_group_sha256": ref.sha(
            PARENT / "runs/R1/exceptional_group.json"),
        "builder_sha256": ref.sha(Path(__file__)),
        "build_wall_seconds": time.perf_counter() - started,
        "peak_rss_bytes": peak_bytes(),
    }
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("policy", "status", "formula_sha256", "stats",
                       "build_wall_seconds", "peak_rss_bytes")},
                     sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
