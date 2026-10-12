#!/usr/bin/env python3
"""Append exact rational-point trace constraints to Q1475's six CNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1475 = PARENT / "q1475_ordered_leaves"
DESIGN = HERE / "design_protocol.json"
MANIFEST = HERE / "input_manifest.json"
OUTPUT = HERE / "inputs"
CASES = (
    "n53_pinned_sorted", "n83_pinned_sorted", "n53_full_coset",
    "n83_planted_unpinned", "n53_ordinary", "n83_ordinary",
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def xor_gate(a: int, b: int, out: int) -> list[list[int]]:
    """Four-clause equivalence out = a XOR b."""
    return [[-a, -b, -out], [-a, b, out], [a, -b, out],
            [a, b, -out]]


def gate_self_test() -> None:
    clauses = xor_gate(1, 2, 3)
    for a, b, out in itertools.product((False, True), repeat=3):
        values = {1: a, 2: b, 3: out}
        allowed = all(any(values[abs(lit)] == (lit > 0)
                          for lit in row) for row in clauses)
        assert allowed == (out == (a ^ b))


def parity_clauses(meta: dict, targets_raw: bytes,
                   first_aux: int) -> tuple[int, list[list[int]], dict]:
    """The three additivity equations; target parity is selector gated."""
    gate_self_test()
    n = meta["degree_n"]
    leaves = meta["leaf_variables"]
    mids = meta["pair_mid_variables"]
    selector = meta["target_selector_variables"]
    assert len(leaves) == 4 and len(mids) == 2
    assert all(len(row) == n for row in leaves + mids)
    assert 0 < len(selector) < 16
    rows = targets_raw.decode("ascii").splitlines()
    header = rows[0].split()
    assert header == ["Q1423TARGETS1", str(n), str(len(rows) - 1)]
    targets = [int(encoded, 16) for encoded in rows[1:]]
    assert len(targets) == meta["target_preimage_x_count"]
    assert all(0 < x < 1 << n for x in targets)

    variables = first_aux - 1
    clauses: list[list[int]] = []

    def chain(bits: list[int]) -> int:
        nonlocal variables
        assert len(bits) >= 2
        carry = bits[0]
        for bit in bits[1:]:
            variables += 1
            clauses.extend(xor_gate(carry, bit, variables))
            carry = variables
        return carry

    for pair in (0, 1):
        parity = chain(leaves[2 * pair] + leaves[2 * pair + 1] +
                       mids[pair])
        clauses.append([-parity])
    final_parity = chain(mids[0] + mids[1])
    parity_counts = [0, 0]
    for choice, target in enumerate(targets):
        trace = target.bit_count() & 1
        parity_counts[trace] += 1
        # The first literals are false exactly for selector == choice.
        guard = [(-bit if choice >> j & 1 else bit)
                 for j, bit in enumerate(selector)]
        clauses.append(guard + ([final_parity] if trace else [-final_parity]))
    return variables, clauses, {
        "pair_trace_equations": 2,
        "target_trace_equations": len(targets),
        "target_trace_zero_count": parity_counts[0],
        "target_trace_one_count": parity_counts[1],
        "trace_encoding": "XOR of native normal-basis coordinate bits",
    }


def render() -> tuple[dict, dict[str, dict[str, bytes]]]:
    design = json.loads(DESIGN.read_text())
    parent = json.loads((Q1475 / "input_manifest.json").read_text())
    assert design["proposal_id"] == "Q1476"
    assert sha(Q1475 / "protocol.json") == design[
        "parent_q1475_protocol_sha256"]
    assert sha(Q1475 / "input_manifest.json") == design[
        "parent_q1475_input_manifest_sha256"]
    assert set(parent["cases"]) == set(design["run_order"]) == set(CASES)
    assert design["run_order"] == list(CASES)
    result = {
        "kind": "q1476_trace_syndrome_inputs",
        "proposal_id": "Q1476", "candidate_id": None, "run_id": None,
        "isogeny": "none", "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(DESIGN), "cases": {},
    }
    outputs: dict[str, dict[str, bytes]] = {}
    for name in design["run_order"]:
        source = Q1475 / "inputs" / name
        prior = parent["cases"][name]
        for leaf, digest in prior["input_sha256"].items():
            assert sha(source / leaf) == digest, (name, leaf)
        raw = gzip.decompress((source / "system.cnf.gz").read_bytes())
        meta = json.loads((source / "meta.json").read_text())
        targets = (source / "targets.txt").read_bytes()
        variable_map = (source / "variables.txt").read_bytes()
        lines = raw.splitlines()
        head = lines[0].split()
        assert head[:2] == [b"p", b"cnf"]
        old_vars, old_clauses = int(head[2]), int(head[3])
        assert len(lines) - 1 == old_clauses
        assert all(line.endswith(b" 0") for line in lines[1:])
        new_vars, added, trace_info = parity_clauses(
            meta, targets, old_vars + 1)
        header = f"p cnf {new_vars} {old_clauses + len(added)}\n".encode()
        appended = b"".join((" ".join(map(str, row)) + " 0\n").encode()
                            for row in added)
        updated = header + b"\n".join(lines[1:]) + b"\n" + appended
        assert len(updated.splitlines()) - 1 == old_clauses + len(added)
        n = meta["degree_n"]
        exact = design["curves"][str(n)]
        assert all(meta[key] == exact[key] for key in
                   ("curve_id", "factor_base_actual_B", "folded_columns_K",
                    "factor_base_enumerated_set_sha256"))
        assert meta["workload_id"] == prior["workload_id"]
        meta = dict(meta)
        meta.update({
            "proposal_id": "Q1476", "case": name,
            "point_decomposition_stage_code": "PDP4hybrid",
            "trace_syndrome": trace_info,
            "parent_proposal_id": "Q1475",
            "parent_input_sha256": prior["input_sha256"],
        })
        files = {
            "system.cnf.gz": gzip.compress(updated, mtime=0),
            "variables.txt": variable_map,
            "targets.txt": targets,
            "meta.json": (json.dumps(meta, sort_keys=True,
                                     indent=2) + "\n").encode(),
        }
        result["cases"][name] = {
            "curve_id": exact["curve_id"], "degree_n": n,
            "factor_base_actual_B": exact["factor_base_actual_B"],
            "folded_columns_K": exact["folded_columns_K"],
            "factor_base_enumerated_set_sha256": exact[
                "factor_base_enumerated_set_sha256"],
            "public_target": meta["public_target"],
            "input_role": meta["input_role"],
            "leaves_pinned": meta["leaves_pinned"],
            "workload_id": meta["workload_id"],
            "parent_input_sha256": prior["input_sha256"],
            "target_preimage_x_count": len(targets.decode().splitlines()) - 1,
            "cnf_variables": new_vars,
            "cnf_clauses": old_clauses + len(added),
            "added_trace_clauses": len(added),
            "trace_syndrome": trace_info,
            "cnf_sha256": sha_bytes(updated),
            "input_sha256": {leaf: sha_bytes(payload)
                             for leaf, payload in files.items()},
        }
        outputs[name] = files
    return result, outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest, outputs = render()
    if args.check:
        assert manifest == json.loads(MANIFEST.read_text())
        for name, files in outputs.items():
            for leaf, data in files.items():
                assert (OUTPUT / name / leaf).read_bytes() == data
    else:
        assert not MANIFEST.exists() and not OUTPUT.exists()
        MANIFEST.write_text(json.dumps(manifest, sort_keys=True,
                                       indent=2) + "\n")
        OUTPUT.mkdir()
        for name, files in outputs.items():
            (OUTPUT / name).mkdir()
            for leaf, data in files.items():
                (OUTPUT / name / leaf).write_bytes(data)
    print(json.dumps({"status": "pass", "cases": list(outputs)}), flush=True)


if __name__ == "__main__":
    main()
