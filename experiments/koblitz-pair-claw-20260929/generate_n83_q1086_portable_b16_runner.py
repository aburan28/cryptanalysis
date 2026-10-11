#!/usr/bin/env python3
"""Derive a 16-bit-only ARM wrapper from the frozen Q1061 portable runner."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "run_n83_portable_chunk.py"
ATTEMPT1 = HERE / "runs/n83_q1086_b16_arm_control_plan.json"
OLD = b"    assert args.bits_per_key == 20\n"
NEW = b"    assert args.bits_per_key == 16\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def derived_bytes():
    plan = json.loads(ATTEMPT1.read_text())
    assert plan["proposal_id"] == "Q1086"
    assert plan["executable_proposal_id"] == "Q1061"
    assert plan["bits_per_key"] == 16
    original = FROZEN.read_bytes()
    assert sha(original) == plan["wrapper_source_sha256"]
    assert original.count(OLD) == 1
    derived = original.replace(OLD, NEW)
    assert derived.count(NEW) == 1
    return derived


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.resolve() == HERE.resolve(), (
        "derived runner must stay beside its source imports")
    assert not args.out.exists(), "refusing to overwrite a derived runner"
    result = derived_bytes()
    args.out.write_bytes(result)
    print(json.dumps({"derived_runner": str(args.out),
                      "sha256": sha(result),
                      "single_edit": "assert args.bits_per_key == 16"}))


if __name__ == "__main__":
    main()
