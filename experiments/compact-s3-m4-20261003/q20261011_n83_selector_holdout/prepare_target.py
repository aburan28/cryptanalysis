#!/usr/bin/env python3
"""Create a frozen-seed N83 holdout using Q1472's exact formula generator."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1472 = PARENT / "q20261011_wdsat_phase_restart"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not (HERE / "target.json").exists()
    frozen = json.loads((HERE / "input_freeze.json").read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    assert frozen["proposal_id"] == protocol["proposal_id"] == "Q1476"
    assert frozen["protocol_sha256"] == sha(HERE / "protocol.json")
    assert frozen["prepare_target_source_sha256"] == sha(Path(__file__))
    assert frozen["q1472_generator_sha256"] == sha(Q1472 / "prepare_target.py")
    assert frozen["runtime_info_sha256"] == sha(HERE / "sage_runtime_info.json")
    spec = importlib.util.spec_from_file_location("q1472_generator_for_q1476",
                                                  Q1472 / "prepare_target.py")
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.HERE = HERE
    generator.SEED = protocol["target_generation_seed"]
    generator.KERNEL_SEED = protocol["cofactor_kernel_seed"]
    generator.main()
    target_path = HERE / "target.json"
    target = json.loads(target_path.read_text())
    prior = json.loads((Q1472 / "target.json").read_text())
    assert target["proposal_id"] == "Q1472"
    assert target["source_sha256"] == frozen["q1472_generator_sha256"]
    assert target["workload_record"]["target_generation"]["seed"] == protocol[
        "target_generation_seed"]
    assert target["curve_id"] == protocol["curve_id"]
    assert target["factor_base_actual_B"] == protocol["factor_base_actual_B"]
    assert target["factor_base_folded_columns_K"] == protocol[
        "factor_base_folded_columns_K"]
    assert target["public_target"] != prior["public_target"]
    assert target["workload_id"] != prior["workload_id"]
    target["proposal_id"] = "Q1476"
    target["generator_source_sha256"] = target.pop("source_sha256")
    target["source_sha256"] = sha(Path(__file__))
    target["input_freeze_sha256"] = sha(HERE / "input_freeze.json")
    target["q1472_target_sha256"] = sha(Q1472 / "target.json")
    target_path.write_text(json.dumps(target, indent=2, sort_keys=True) + "\n")
    print("Q1476 holdout", target["workload_id"],
          target["original_variables"], target["derived_variables"])


if __name__ == "__main__":
    main()
