"""Verify the odd-degree Artin--Schreier half-trace replacement."""

import hashlib
import json
import random
from pathlib import Path

from circuit import Field
from run import HERE, save


def main():
    field = Field()
    rng = random.Random(20261011)
    inputs = [0, 1, *[1 << bit for bit in range(41)]]
    inputs.extend(rng.getrandbits(41) for _ in range(100))
    for value in inputs:
        trace = field.trace(value)
        root = field.halftrace(value)
        assert field.square(root) ^ root == value ^ trace
        if trace == 0:
            assert field.square(root ^ 1) ^ (root ^ 1) == value
    control = json.loads((HERE / "control_result.json").read_text())
    assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
    assert len(control["branch_choices"]) == 3
    assert all(choice in (0, 1) for choice in control["branch_choices"])
    record = {"status": "PASS_143_HALFTRACE_IDENTITIES_AND_PUBLIC_BRANCH_CHOICES",
              "field": "GF(2)[t]/(t^41+t^3+1)", "seed": 20261011,
              "tested_values": len(inputs),
              "public_branch_choices": control["branch_choices"],
              "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                for path in (Path(__file__), HERE / "circuit.py",
                                             HERE / "control_result.json")}}
    save(HERE / "halftrace_audit.json", record)
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
