#!/usr/bin/env python3
"""Exploratory ABBA prefix comparison on one frozen ordinary complement."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
BASE = PARENT / "bases/n83_weight5_full_point_orbits.bin"
INPUTS = PARENT / "q20261012_n83_complement_pair_probe/frozen_inputs.json"
BIN = Path("/Volumes/SSD990/llm/tmp/q1501-build")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    selected = json.loads(INPUTS.read_text())["inputs"]["selected"]
    point = selected["complements"][0]
    rows = []
    for name in ("native_signed", "native_deferred_y", "native_deferred_y", "native_signed"):
        binary = BIN / name
        args = [str(binary), str(BASE), point["x_onb_hex"], point["y_onb_hex"],
                "2000000", "512"]
        p = subprocess.run(args, text=True, capture_output=True, timeout=90)
        assert p.returncode == 0, p.stderr
        lines = p.stdout.splitlines()
        result = json.loads(lines[-1])
        assert result["scanned"] == 4000000 and result["hits"] == 0
        rows.append({"binary": name, "binary_sha256": sha(binary),
                     "status": "COMPLETE", "scan_seconds": result["scan_seconds"],
                     "checksum_hex": result["checksum_hex"],
                     "exceptional_pairs": result["exceptional_pairs"]})
        print(name, result["scan_seconds"], flush=True)
    assert len({r["checksum_hex"] for r in rows}) == 1
    (HERE / "paired_probe.json").write_text(json.dumps({
        "proposal_id": "Q1505", "candidate_id": None, "run_id": None,
        "curve_id": "EC1N83Ckb1h876c2921cb64", "isogeny": "none",
        "host_isolation": "none; wall times exploratory",
        "source_sha256": sha(Path(__file__)), "inputs_sha256": sha(INPUTS),
        "base_sha256": sha(BASE), "pair_prefix_count": 2000000,
        "batch_pairs": 512, "rows": rows}, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
