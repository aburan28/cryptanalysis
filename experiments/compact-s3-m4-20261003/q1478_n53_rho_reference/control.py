#!/usr/bin/env python3
"""Exhaustive small-prime collision algebra controls for Q1478."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "control_result.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    checks = 0
    for prime in (101, 103, 127):
        rng = random.Random(14780053 + prime)
        for log_q in range(1, prime):
            for _ in range(20):
                old_a = rng.randrange(prime)
                old_b = rng.randrange(prime)
                new_b = rng.randrange(prime)
                if new_b == old_b:
                    new_b = (new_b + 1) % prime
                new_a = (old_a + (old_b - new_b) * log_q) % prime
                old_point = (old_a + old_b * log_q) % prime
                new_point = (new_a + new_b * log_q) % prime
                assert old_point == new_point
                numerator = (old_a - new_a) % prime
                denominator = (new_b - old_b) % prime
                assert denominator
                recovered = numerator * pow(denominator, prime - 2,
                                            prime) % prime
                assert recovered == log_q
                checks += 1
    return {
        "kind": "q1478_small_prime_collision_controls",
        "proposal_id": "Q1478", "candidate_id": None,
        "isogeny": "none", "status": "passed",
        "toy_prime_orders": [101, 103, 127],
        "collision_equation_checks": checks,
        "source_sha256": sha(Path(__file__)),
        "design_protocol_sha256": sha(HERE / "design_protocol.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert args.emit != args.check
    result = build()
    if args.emit:
        assert not OUT.exists(), "refuse overwrite"
        OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    else:
        assert result == json.loads(OUT.read_text())
    print(json.dumps({"status": "pass", "checks": result[
        "collision_equation_checks"]}), flush=True)


if __name__ == "__main__":
    main()
