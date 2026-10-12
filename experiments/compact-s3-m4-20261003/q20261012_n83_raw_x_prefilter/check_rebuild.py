#!/usr/bin/env python3
"""Compare a source rebuild's exact outputs with frozen Q1512 controls."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(binary, x, y, pairs, batch, bits, hashes):
    args = [str(binary), str(BASE), x, y, str(pairs), str(batch),
            str(bits), str(hashes)]
    process = subprocess.run(args, capture_output=True, text=True, timeout=30)
    assert process.returncode == 0, process.stderr
    return {"command": args, "stdout": process.stdout,
            "native": json.loads(process.stdout.splitlines()[-1])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((HERE / "protocol.json").read_text())
    frozen = json.loads((HERE / "result.json").read_text())
    controls = json.loads((HERE / "deep_control.json").read_text())
    assert args.binary.exists()
    rows = []
    for sign in (0, 1):
        reference = next(row for row in controls["rows"] if row["sign"] == sign and row["mode"] == [28, 4])
        x, y = reference["target_onb_xy_hex"]
        row = call(args.binary, x, y, controls["base_scan_position"] + 1, 512, 28, 4)
        assert row["native"]["hits"] == reference["native"]["hits"]
        assert row["native"]["raw_x_checksum_hex"] == reference["native"]["raw_x_checksum_hex"]
        assert row["native"]["canonical_calls"] == reference["native"]["canonical_calls"]
        rows.append({"kind": "deep_control", "sign": sign, **row})
    reference = next(row for row in frozen["rows"] if row["panel"] == "screen" and
                     row["bloom_log2_bits"] == 28 and row["bloom_hashes"] == 4)
    item = protocol["ordinary_inputs"]["selected"]
    row = call(args.binary, item["x_onb_hex"], item["y_onb_hex"],
               protocol["screen_pair_count"], protocol["batch_pairs"], 28, 4)
    for key in ("hits", "raw_x_checksum_hex", "canonical_calls",
                "bloom_scan_bit_probes", "bloom_build_bit_sets"):
        assert row["native"][key] == reference["native"][key]
    rows.append({"kind": "ordinary_screen", **row})
    report = {"proposal_id": "Q1512", "kind": "source_rebuild_behavior_check",
              "source_sha256": sha(HERE / "native_prefilter.cpp"),
              "frozen_binary_sha256": protocol["binary_sha256"],
              "rebuild_binary_sha256": sha(args.binary), "rows": rows,
              "checked_status": "PASS"}
    if args.record:
        out = HERE / "rebuild_check.json"
        assert not out.exists()
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("PASS Q1512 source rebuild controls and ordinary prefix",
          report["rebuild_binary_sha256"])


if __name__ == "__main__":
    main()
