#!/usr/bin/env python3
"""Append a sound strict raw-leaf order to frozen chained-S3 CNFs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(PARENT))

from q1438_dense_base.build_formula import encode_map  # noqa: E402

Q1467 = PARENT / "q1467_density_bridge"
Q1474 = PARENT / "q1474_n53_positive_compact"
OUTPUT = HERE / "inputs"
MANIFEST = HERE / "input_manifest.json"
CASES = (
    "n53_pinned_sorted", "n83_pinned_sorted", "n53_full_coset",
    "n83_planted_unpinned", "n53_ordinary", "n83_ordinary",
)
PARENTS = {
    "n53_pinned_sorted": (Q1474, "selected_preimage"),
    "n83_pinned_sorted": (Q1467, "n83_planted_unpinned"),
    "n53_full_coset": (Q1474, "full_coset"),
    "n83_planted_unpinned": (Q1467, "n83_planted_unpinned"),
    "n53_ordinary": (Q1467, "n53_ordinary"),
    "n83_ordinary": (Q1467, "n83_ordinary"),
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def order_clauses(leaves: list[list[int]], first_aux: int) -> tuple[int, list[list[int]]]:
    """Tseitin CNF for x0<x1<x2<x3 in little-endian bit vectors."""
    assert len(leaves) == 4
    n = len(leaves[0])
    assert n > 1 and all(len(row) == n for row in leaves)
    variables = first_aux - 1
    clauses: list[list[int]] = []

    def new() -> int:
        nonlocal variables
        variables += 1
        return variables

    for left, right in zip(leaves, leaves[1:]):
        prefix = None  # equality of all more-significant coordinates
        for j in range(n - 1, -1, -1):
            a, b = left[j], right[j]
            clauses.append(([-a, b] if prefix is None
                            else [-prefix, -a, b]))
            equal = new()
            # equal <-> (a == b)
            clauses.extend(([-a, -b, equal], [a, b, equal],
                            [-a, b, -equal], [a, -b, -equal]))
            if prefix is None:
                prefix = equal
            else:
                next_prefix = new()
                clauses.extend(([-next_prefix, prefix],
                                [-next_prefix, equal],
                                [next_prefix, -prefix, -equal]))
                prefix = next_prefix
        assert prefix is not None
        clauses.append([-prefix])  # forbid equality
    return variables, clauses


def comparator_self_test() -> None:
    # Exhaustively quantify auxiliary assignments on all 3-bit input pairs.
    # Keep two unused rows so this exercises the production three-comparator
    # generator, then inspect the first comparator's clauses only.
    for n in (2, 3):
        leaves = [[1 + k * n + j for j in range(n)] for k in range(4)]
        first = 4 * n + 1
        _, all_clauses = order_clauses(leaves, first)
        per = len(all_clauses) // 3
        clauses = all_clauses[:per]
        last_var = max(abs(lit) for row in clauses for lit in row)
        aux = list(range(first, last_var + 1))
        for a, b in itertools.product(range(1 << n), repeat=2):
            base = {leaves[0][j]: bool(a >> j & 1) for j in range(n)}
            base.update({leaves[1][j]: bool(b >> j & 1) for j in range(n)})
            possible = False
            for values in itertools.product((False, True), repeat=len(aux)):
                model = dict(base)
                model.update(zip(aux, values))
                if all(any(model[abs(lit)] == (lit > 0) for lit in row)
                       for row in clauses):
                    possible = True
                    break
            assert possible == (a < b), (n, a, b)


def source_case(name: str) -> tuple[Path, str, bytes, dict, bytes]:
    parent, key = PARENTS[name]
    folder = parent / "inputs" / key
    raw = gzip.decompress((folder / "system.cnf.gz").read_bytes())
    meta = json.loads((folder / "meta.json").read_text())
    targets = (folder / "targets.txt").read_bytes()
    return folder, key, raw, meta, targets


def pinned_masks(name: str, meta: dict) -> list[int] | None:
    if name == "n53_pinned_sorted":
        manifest = json.loads((Q1474 / "input_manifest.json").read_text())
        values = manifest["raw_witness_leaf_x_masks_onb_hex"]
    elif name == "n83_pinned_sorted":
        values = meta["planted_fixture"]["raw_leaf_x_masks_onb_hex"]
    else:
        return None
    masks = sorted(int(value, 16) for value in values)
    assert len(masks) == len(set(masks)) == 4
    assert all(0 < value < 1 << meta["degree_n"] for value in masks)
    return masks


def render() -> tuple[dict, dict[str, dict[str, bytes]]]:
    comparator_self_test()
    design = json.loads((HERE / "design_protocol.json").read_text())
    assert design["run_order"] == list(CASES)
    assert sha(Q1474 / "protocol.json") == design[
        "parent_q1474_protocol_sha256"]
    assert sha(Q1467 / "solver_protocol.json") == design[
        "parent_q1467_solver_protocol_sha256"]
    parent_protocols = {
        Q1474: json.loads((Q1474 / "protocol.json").read_text()),
        Q1467: json.loads((Q1467 / "solver_protocol.json").read_text()),
    }
    metadata = {
        "kind": "q1475_ordered_leaf_inputs", "proposal_id": "Q1475",
        "candidate_id": None, "run_id": None, "isogeny": "none",
        "point_decomposition_stage_code": "PDP4hybrid",
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
        "cases": {},
    }
    outputs = {}
    for name in CASES:
        folder, parent_key, raw, source_meta, targets = source_case(name)
        parent_root = PARENTS[name][0]
        parent_record = (parent_protocols[parent_root]["cases"][parent_key]
                         if parent_root == Q1474 else
                         parent_protocols[parent_root]["cells"][parent_key])
        for leaf, expected in parent_record["input_sha256"].items():
            assert sha(folder / leaf) == expected, (name, leaf)
        n = source_meta["degree_n"]
        assert design["curves"][str(n)]["curve_id"] == source_meta[
            "curve_id"]
        assert design["curves"][str(n)]["factor_base_actual_B"] == (
            source_meta["factor_base_actual_B"])
        assert design["curves"][str(n)]["folded_columns_K"] == (
            source_meta["folded_columns_K"])
        assert design["curves"][str(n)][
            "factor_base_enumerated_set_sha256"] == source_meta[
                "factor_base_enumerated_set_sha256"]
        lines = raw.splitlines()
        head = lines[0].split()
        assert head[:2] == [b"p", b"cnf"]
        old_variables, old_clauses = int(head[2]), int(head[3])
        assert len(lines) - 1 == old_clauses
        assert all(line.endswith(b" 0") for line in lines[1:])
        masks = pinned_masks(name, source_meta)
        new_variables, added = order_clauses(source_meta[
            "leaf_variables"], old_variables + 1)
        if masks is not None:
            for bits, mask in zip(source_meta["leaf_variables"], masks):
                added.extend(([bit if mask >> j & 1 else -bit]
                              for j, bit in enumerate(bits)))
        new_header = f"p cnf {new_variables} {old_clauses + len(added)}\n".encode()
        appended = b"".join((" ".join(map(str, row)) + " 0\n").encode()
                            for row in added)
        updated = new_header + b"\n".join(lines[1:]) + b"\n" + appended
        assert len(updated.splitlines()) - 1 == old_clauses + len(added)
        parent_workload = source_meta["workload_id"]
        if masks is None:
            workload = parent_workload
            workload_record = None  # exact parent record is source-bound
        else:
            workload_record = {
                "curve_id": source_meta["curve_id"],
                "public_target": source_meta["public_target"],
                "parent_workload_id": parent_workload,
                "target_input_sha256": sha_bytes(targets),
                "sorted_raw_x_pins_onb_hex": [format(x, "x") for x in masks],
                "target_count": 1,
                "cache_state": "cold_compact_s3_control",
            }
            workload = sha_bytes(canonical(workload_record))[:12]
        meta = dict(source_meta)
        meta.update({
            "proposal_id": "Q1475", "case": name,
            "point_decomposition_stage_code": "PDP4hybrid",
            "symmetry_constraint": "strictly_increasing_raw_x_onb_integer",
            "parent_proposal_id": source_meta["proposal_id"],
            "parent_case": parent_key,
            "parent_workload_id": parent_workload,
            "workload_id": workload,
            "leaves_pinned": masks is not None,
            "sorted_pinned_raw_x_onb_hex": ([format(x, "x") for x in masks]
                                              if masks else None),
        })
        files = {
            "system.cnf.gz": gzip.compress(updated, mtime=0),
            "variables.txt": encode_map(meta),
            "targets.txt": targets,
            "meta.json": (json.dumps(meta, sort_keys=True,
                                     indent=2) + "\n").encode(),
        }
        metadata["cases"][name] = {
            "curve_id": meta["curve_id"], "degree_n": n,
            "factor_base_actual_B": meta["factor_base_actual_B"],
            "folded_columns_K": meta["folded_columns_K"],
            "factor_base_enumerated_set_sha256": meta[
                "factor_base_enumerated_set_sha256"],
            "public_target": meta["public_target"],
            "input_role": meta["input_role"],
            "leaves_pinned": masks is not None,
            "workload_id": workload,
            "workload_record": workload_record,
            "parent_workload_id": parent_workload,
            "parent_case": parent_key,
            "parent_input_sha256": {
                leaf: sha(folder / leaf) for leaf in
                ("system.cnf.gz", "variables.txt", "targets.txt", "meta.json")},
            "target_preimage_x_count": meta["target_preimage_x_count"],
            "cnf_variables": new_variables,
            "cnf_clauses": old_clauses + len(added),
            "added_order_or_pin_clauses": len(added),
            "cnf_sha256": sha_bytes(updated),
            "input_sha256": {leaf: sha_bytes(payload)
                             for leaf, payload in files.items()},
        }
        outputs[name] = files
    return metadata, outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    metadata, outputs = render()
    if args.check:
        assert metadata == json.loads(MANIFEST.read_text())
        for name, files in outputs.items():
            assert all((OUTPUT / name / leaf).read_bytes() == data
                       for leaf, data in files.items()), name
    else:
        assert not MANIFEST.exists() and not OUTPUT.exists()
        MANIFEST.write_text(json.dumps(metadata, sort_keys=True,
                                       indent=2) + "\n")
        OUTPUT.mkdir()
        for name, files in outputs.items():
            (OUTPUT / name).mkdir()
            for leaf, data in files.items():
                (OUTPUT / name / leaf).write_bytes(data)
    print(json.dumps({"status": "pass", "cases": list(CASES)}), flush=True)


if __name__ == "__main__":
    main()
