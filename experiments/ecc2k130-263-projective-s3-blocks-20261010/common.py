#!/usr/bin/env python3
"""Pinned parent inputs and exact XCNF composition for the block controls."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "ecc2k130-263-projective-s3-sat-20261010"
sys.path.insert(0, str(PARENT))
import build_control as circuit  # noqa: E402
import make_cells as parent_cells  # noqa: E402
import verify_model as model  # noqa: E402


ref = circuit.ref
SPEC = importlib.util.spec_from_file_location("pinned_parent_sat_audit",
                                               PARENT / "audit.py")
if SPEC is None or SPEC.loader is None:
    raise ImportError("parent SAT auditor is unavailable")
parent_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent_audit)


def load_config():
    config = ref.read(HERE / "CONFIG.json")
    if config["schema"] != "ecc2k130-263-projective-s3-search-blocks-v1":
        raise ValueError("search-block config schema changed")
    for name, digest in config["parent_sha256"].items():
        if ref.sha(PARENT / name) != digest:
            raise ValueError("parent source/input digest changed: " + name)
    parent_config = ref.read(PARENT / "CONFIG.json")
    parent_result = ref.read(PARENT / "runs/R1/audit.json")
    if parent_result["status"] != "PASS_FIXED_EXCEPTIONAL_SAT_AND_GROUP_REPLAY":
        raise ValueError("parent SAT group-replay gate has not passed")
    for policy in config["policies"]:
        cells = parent_result["policies"][policy]["cells"]
        if (cells["positive"]["status"] != "SAT_VERIFIED_GROUP"
                or cells["free"]["status"] != "BOUNDED_UNKNOWN"):
            raise ValueError("parent fixed or mask-only status changed")
    if (config["modes"] != ["intermediate_free", "leaf_free"]
            or config["ordered_cells"] != [
                "source/intermediate_free", "source/leaf_free",
                "descendant_native/intermediate_free",
                "descendant_native/leaf_free"]):
        raise ValueError("frozen policy or mode order changed")
    return config, parent_config, parent_result


def parent_inputs(policy, config, parent_config):
    if policy not in config["policies"]:
        raise ValueError("unexpected curve policy")
    group_receipt = parent_audit.check_parent(parent_config)
    build, base, inputs, base_row = parent_audit.check_build(
        policy, PARENT / "runs/R1", parent_config)
    if base_row["gzip_sha256"] != config["parent_sha256"][
            f"runs/R1/{policy}_control_base.xcnf.gz"]:
        raise ValueError("parent base archive identity changed")
    return group_receipt["policies"][policy], build, base, inputs, base_row


def write_json(path, item):
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item, sort_keys=True, indent=2) + "\n")
