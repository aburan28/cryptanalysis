"""Shared deterministic XCNF and blocking operations for Q1449."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xcnf_bytes(formula) -> bytes:
    """Use the original Formula writer, preserving native XOR rows."""
    with tempfile.TemporaryDirectory(prefix="q1449-xcnf-") as directory:
        path = Path(directory) / "system.xcnf"
        formula.write(path)
        return path.read_bytes()


def blocked_assignment(formula, meta, model: dict[int, bool]) -> dict:
    """Exclude only this ordered leaf-x tuple and target selector."""
    leaf_bits = meta["leaf_x_variables"]
    selector_bits = meta["target_selector_variables"]
    variables = [bit for row in leaf_bits for bit in row] + selector_bits
    assert len(variables) == len(set(variables))
    assert all(bit in model for bit in variables)
    clause = [-bit if model[bit] else bit for bit in variables]
    assert clause not in formula.clauses
    formula.clauses.append(clause)
    masks = [sum(1 << i for i, bit in enumerate(row) if model[bit])
             for row in leaf_bits]
    selector = sum(1 << i for i, bit in enumerate(selector_bits)
                   if model[bit])
    return {"raw_leaf_x": masks, "target_selector_choice": selector,
            "clause_sha256": sha_bytes((" ".join(map(str, clause)) + " 0\n").encode())}
