#!/usr/bin/env python3
"""Freeze Q1457 generator setup inputs before its native measurement."""
from __future__ import annotations
import hashlib
import json
import random
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIR = HERE.parent / "q20261011_n53_native_pair"
FULL = HERE.parent / "q20261011_n53_native_full"
HORIZON = HERE.parent / "q20261011_n53_query_horizon"
TEMP = Path("/private/tmp/q1457_n53_setup")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    assert not TEMP.exists() and not (HERE / "freeze.json").exists()
    protocol = json.loads((HERE / "protocol.json").read_text())
    exported = json.loads((PAIR / "export_receipt.json").read_text())
    prior = json.loads((FULL / "native_measurement.json").read_text())
    horizon = json.loads((HORIZON / "freeze.json").read_text())
    assert protocol["curve_id"] == exported["curve_id"] == prior["curve_id"]
    assert protocol["factor_base_enumerated_set_sha256"] == exported["factor_base_enumerated_set_sha256"]
    assert protocol["point_decomposition"]["query_seed"] == 530931
    for name,record in exported["files"].items():
        path = PAIR / "inputs" / name
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    TEMP.mkdir()
    for name in exported["files"]:
        if name != "queries.bin":
            (TEMP / name).symlink_to(PAIR / "inputs" / name)
    cap = protocol["point_decomposition"]["setup_query_cap"]
    seed = protocol["point_decomposition"]["query_seed"]
    rng = random.Random(seed)
    digest = hashlib.sha256()
    prefix = hashlib.sha256()
    with (TEMP / "queries.bin").open("wb") as stream:
        for i in range(cap):
            pair = struct.pack("<HH", rng.randrange(protocol["factor_base_actual_B"]),
                               rng.randrange(protocol["factor_base_actual_B"]))
            stream.write(pair)
            digest.update(pair)
            if i < 5000000:
                prefix.update(pair)
    assert prefix.hexdigest() == horizon["query_file_sha256"]
    freeze = {"proposal_id": "Q1457", "candidate_id": None, "run_id": None,
              "curve_id": protocol["curve_id"], "isogeny": "none",
              "protocol_sha256": sha(HERE / "protocol.json"),
              "prepare_source_sha256": sha(Path(__file__)),
              "native_source_sha256": sha(HERE / "native_sweep.cpp"),
              "field_source_sha256": sha(PAIR / "native_field53.hpp"),
              "q1454_export_receipt_sha256": sha(PAIR / "export_receipt.json"),
              "q1455_measurement_sha256": sha(FULL / "native_measurement.json"),
              "q1456_freeze_sha256": sha(HORIZON / "freeze.json"),
              "query_count": cap, "query_seed": seed,
              "query_file_sha256": digest.hexdigest(),
              "prefix_5000000_sha256": prefix.hexdigest(),
              "setup_generator_onb_xy": protocol["generator_onb_xy"],
              "base_input_sha256": exported["files"]["base.bin"]["sha256"]}
    (HERE / "freeze.json").write_text(json.dumps(freeze,indent=2,sort_keys=True)+"\n")
    print("FROZEN", cap, digest.hexdigest())


if __name__ == "__main__":
    main()
