#!/usr/bin/env python3
"""Check source binding, holdout replay, and paired point-kernel counts."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from make_inputs import SOURCES
from verify_inputs import main as verify_inputs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FREEZE = "0c346ac93a7d87f757f7f9917f2bc95213a2c614"
FROZEN = (
    "PROOF.md", "build_atlas.py", "make_inputs.py", "verify_inputs.py",
    "verify_group.py", "atlas-r640-d640.bin", "atlas-r640-d391.bin",
    "atlas-receipt.json",
)


def digest(raw):
    return sha256(raw).hexdigest()


def main():
    verify_inputs()
    source_hashes = {}
    for name in FROZEN:
        relative = f"experiments/prime-j0-mixed-radix640-20261010/{name}"
        committed = subprocess.run(["git", "show", f"{FREEZE}:{relative}"],
                                   cwd=ROOT, capture_output=True, check=True).stdout
        actual = (HERE / name).read_bytes()
        assert committed == actual, name
        source_hashes[name] = digest(actual)
    atlas = json.loads((HERE / "atlas-receipt.json").read_bytes())
    group = json.loads((HERE / "group-check.json").read_bytes())
    assert atlas["schema"] == group["schema"] == 1
    assert group["status"] == "passed"
    assert atlas["atlas_generator_sha256"] == source_hashes["build_atlas.py"]
    assert group["source_sha256"] == source_hashes["verify_group.py"]
    assert group["atlas_sha256"] == {
        "512": atlas["prior_width9_atlas_sha256"],
        "640": atlas["atlases"]["640"]["atlas_sha256"],
        "391": atlas["atlases"]["391"]["atlas_sha256"],
    }
    assert atlas["point_slots"] == 415_190
    assert atlas["point_payload_bytes"] == 26_572_160
    assert atlas["termination_margin"] == (
        "26508597186945872034846785349754346156954426674993113148162584666361413311")
    panel = group["panel"]
    inputs = HERE / "fresh-inputs.json"
    assert panel["cases"] == 4096 and panel["input_sha256"] == digest(inputs.read_bytes())
    assert panel["mixed_additions"] == 53_248
    assert panel["bucket_terms"] == [29_629, 27_715]
    assert panel["gauge_rotations"] == 15_094

    prior = HERE.parent / "prime-j0-bound-budget15-gauge-20261010"
    sys.path.insert(0, str(prior))
    from verify_ops import operation_counts
    scalars = json.loads(inputs.read_bytes())["scalars_hex"]
    baseline = operation_counts(scalars)
    assert baseline["mixed_additions"] == 57_344
    assert baseline["gauge_rotations"] == 15_351
    saved_mixed = baseline["mixed_additions"] - panel["mixed_additions"]
    saved_rotations = baseline["gauge_rotations"] - panel["gauge_rotations"]
    assert saved_mixed == 4096 and saved_rotations == 257
    # The paired point-kernel model charges 8M+2S per ordinary XYZZ mixed
    # addition and 23 source-loop products per Solinas rotation. It excludes
    # the extra radix-640 integer division and all startup costs.
    saved_products_model = 36 * 10 * saved_mixed + 23 * saved_rotations
    assert saved_products_model == 1_480_471
    record = {
        "schema": 1,
        "timing_class": "source_operation_model_only",
        "source_freeze_commit": FREEZE,
        "source_sha256": source_hashes,
        "input_sha256": digest(inputs.read_bytes()),
        "group_check_sha256": digest((HERE / "group-check.json").read_bytes()),
        "paired_cases": 4096,
        "mixed_radix640": {"mixed_additions": panel["mixed_additions"],
                           "gauge_rotations": panel["gauge_rotations"]},
        "frontier15_gauge": baseline,
        "saved_mixed_additions": saved_mixed,
        "saved_gauge_rotations": saved_rotations,
        "point_kernel_source_products_saved_model": saved_products_model,
        "excluded_from_model": ["radix640_integer_division", "table_setup",
                                "input_loading", "host_wall_time"],
    }
    target = HERE / "paired-ops.json"
    if sys.argv[1:] == ["--write"]:
        assert not target.exists()
        target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    else:
        assert not sys.argv[1:]
        assert json.loads(target.read_bytes()) == record
    print(f"radix640_verified=1 cases=4096 saved_mixed={saved_mixed} "
          f"point_kernel_products_saved_model={saved_products_model}")


if __name__ == "__main__":
    main()
