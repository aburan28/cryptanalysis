#!/usr/bin/env python3
"""Bind the temporary field counters to the frozen source and scalar panel."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from run_replay import HERE, parse
from verify_inputs import main as verify_inputs


ROOT = HERE.parent.parent
NAMES = ("frontier15_bound_budget", "frontier16_beta_solinas")


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    verify_inputs()
    source = json.loads((HERE / "source-receipt.json").read_text())
    replay = json.loads((HERE / "replay-result.json").read_text())
    assert replay["source_freeze_commit"] == source["source_freeze_commit"]
    patch = HERE / "ops-diagnostic.patch"
    subprocess.run(["git", "apply", "--check", str(patch)], cwd=ROOT,
                   check=True, capture_output=True)
    counts_path = HERE / "operation-counts.json"
    counts_hash = digest(counts_path)
    subprocess.run([sys.executable, str(HERE / "count_ops.py")], cwd=ROOT,
                   check=True, capture_output=True)
    assert digest(counts_path) == counts_hash
    counts = json.loads(counts_path.read_text())
    assert counts["fresh"]["count"] == counts["prior"]["count"] == 4096
    assert counts["fresh"]["input_sha256"] == digest(HERE / "fresh-inputs.json")
    for label, path in (("full8", HERE.parent / "prime-j0-tau-frontier-20261010/w8-d256/atlas-w8.bin"),
                        ("full9", HERE / "atlas-w9.bin"),
                        ("final9", HERE.parent / "prime-j0-tau-power16-20261010/atlas-w9.bin")):
        assert counts["atlas_sha256"][label] == digest(path)
    log = HERE / "ops-diagnostic.log"
    lines = log.read_text().splitlines()
    assert any("test result: ok. 1 passed" in line for line in lines)
    records = {row["mode"]: row for line in lines if line.startswith("mode=")
               for row in [parse(line)]}
    assert set(records) == set(NAMES)
    for name in NAMES:
        row = records[name]
        assert int(row["cases"]) == 4096
        assert int(row["mixed_additions"]) == counts["fresh"]["modes"][name]["total_mixed_additions"]
        model = 36 * (int(row["point_kernel_generic_mul"]) +
                      int(row["point_kernel_square"])) + 23 * int(row["point_kernel_solinas_mul"])
        assert model == int(row["source_limb_products"])
    candidate = records[NAMES[0]]
    baseline = records[NAMES[1]]
    saved = int(baseline["source_limb_products"]) - int(candidate["source_limb_products"])
    assert saved > 0
    receipt = {"schema": 1, "source_freeze_commit": source["source_freeze_commit"],
               "patch_sha256": digest(patch), "log_sha256": digest(log),
               "operation_counts_sha256": counts_hash,
               "fresh_input_sha256": counts["fresh"]["input_sha256"],
               "source_limb_products_saved": saved, "modes": records}
    destination = HERE / "ops-diagnostic.json"
    if sys.argv[1:] == ["--write"]:
        assert not destination.exists()
        destination.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    else:
        assert json.loads(destination.read_text()) == receipt
    print(f"ops_verified=1 cases=4096 source_limb_products_saved={saved}")


if __name__ == "__main__":
    main()
