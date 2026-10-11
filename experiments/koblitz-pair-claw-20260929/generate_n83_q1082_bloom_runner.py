#!/usr/bin/env python3
"""Derive the Q1082 16/20-bit control from the frozen Q1079 runner.

The single source edit changes only Q1079's fixed Bloom-density gate. The
generated runner stays beside its imports and is archived with each CI job.
"""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FROZEN = HERE / "run_n83_zero_run_chunk.py"
PLAN = HERE / "n83_q1082_m28_r24_bloom_paired_plan.json"
OLD = "    assert args.bits_per_key == 20\n"
NEW = "    assert args.bits_per_key in (16, 20)\n"


def derived_bytes():
    plan = json.loads(PLAN.read_text())
    frozen = FROZEN.read_bytes()
    assert hashlib.sha256(frozen).hexdigest() == plan["Q1079_runner_sha256"]
    assert frozen.count(OLD.encode()) == 1
    derived = frozen.replace(OLD.encode(), NEW.encode())
    assert derived.count(NEW.encode()) == 1
    return derived


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.resolve() == HERE.resolve(), (
        "generated runner must stay beside its source imports")
    assert not args.out.exists(), "refusing to overwrite generated runner"
    result = derived_bytes()
    plan = json.loads(PLAN.read_text())
    assert hashlib.sha256(result).hexdigest() == plan[
        "Q1082_derived_runner_sha256"]
    args.out.write_bytes(result)
    print(json.dumps({"generated_runner": str(args.out),
                      "sha256": hashlib.sha256(result).hexdigest()}))


if __name__ == "__main__":
    main()
