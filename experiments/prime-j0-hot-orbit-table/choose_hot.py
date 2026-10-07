#!/usr/bin/env python3
"""Select exactly 64 orbit slots from the old, never-held-out fixtures."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = REPO / "experiments/prime-j0-joint-tau-stream/inputs.json"
EXPECTED_OVERLAPS = {"glv-j0-32": 1373, "j0-56": 2222}
COUNT = 64


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(hist, curve, path):
    process = subprocess.run([str(hist), curve, str(path)],
                             capture_output=True, text=True, check=True)
    rows = [tuple(map(int, line.split(",")))
            for line in process.stdout.strip().splitlines()]
    if len(rows) != 486 or [index for index, _ in rows] != list(range(486)):
        raise ValueError(f"malformed histogram for {curve}")
    counts = [count for _, count in rows]
    if sum(counts) != EXPECTED_OVERLAPS[curve]:
        raise ValueError(f"unexpected training overlap count for {curve}")
    selected = sorted(range(486), key=lambda index: (-counts[index], index))[:COUNT]
    return counts, selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hist", type=Path)
    args = parser.parse_args()
    hist = args.hist.resolve()
    header = HERE / "hot64_selected.h"
    manifest_path = HERE / "selection.json"
    if header.exists() or manifest_path.exists():
        raise SystemExit("selection already exists; refusing to overwrite")
    old = json.loads(OLD.read_text())
    manifest = {
        "schema": 1, "selection_rule": "top64_count_desc_slot_asc",
        "training_manifest_sha256": sha(OLD), "hist_binary_sha256": sha(hist),
        "hist_source_sha256": sha(HERE / "hist.c"),
        "recode_source_sha256": sha(REPO / "src/ec_tau.c"),
        "curves": {},
    }
    lines = ["/* Generated from the old PR #419 fixture; held-out inputs were not used. */",
             "#ifndef CA_HOT64_SELECTED_H", "#define CA_HOT64_SELECTED_H",
             "#include <stdint.h>"]
    for curve, symbol in (("glv-j0-32", "ca_hot64_j0_32"),
                          ("j0-56", "ca_hot64_j0_56")):
        spec = old["curves"][curve]
        path = OLD.parent / spec["file"]
        if sha(path) != spec["sha256"]:
            raise ValueError(f"training input SHA mismatch for {curve}")
        counts, selected = run(hist, curve, path)
        manifest["curves"][curve] = {
            "input_sha256": spec["sha256"], "histogram": counts,
            "selected": selected, "training_overlap_count": sum(counts),
            "training_selected_hits": sum(counts[index] for index in selected),
        }
        lines.append(f"static const uint16_t {symbol}[64] = {{")
        for start in range(0, COUNT, 8):
            lines.append("    " + ", ".join(str(x) for x in selected[start:start + 8]) + ",")
        lines.append("};")
    lines.append("#endif")
    header.write_text("\n".join(lines) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({curve: {"hits": spec["training_selected_hits"],
                              "overlaps": spec["training_overlap_count"]}
                      for curve, spec in manifest["curves"].items()}, sort_keys=True))


if __name__ == "__main__":
    main()
