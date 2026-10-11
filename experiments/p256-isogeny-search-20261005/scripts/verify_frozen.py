#!/usr/bin/env python3
"""Independently replay the frozen structural and toy correctness controls."""

from __future__ import annotations

import json
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from p256_isogeny_search.analysis import structural_report  # noqa: E402
from p256_isogeny_search.registry import load_candidates  # noqa: E402
from p256_isogeny_search.rho import solve_toy_log  # noqa: E402


def load(name: str) -> dict:
    return json.loads((ROOT / "results" / "initial" / name).read_text())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    receipt = json.loads((ROOT / "receipt-initial.json").read_text())
    manifest_path = ROOT / receipt["source"]["integrated_source_manifest"]
    assert sha256(manifest_path) == receipt["source"][
        "integrated_source_manifest_sha256"
    ]
    for line in manifest_path.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        assert sha256(ROOT / relative) == expected, relative
    for relative, expected in receipt["artifacts"].items():
        assert sha256(ROOT / relative) == expected, relative

    frozen_structural = load("structural-report.json")
    frozen_benchmark = load("benchmark.json")
    frozen_toy = load("toy-rho.json")
    replay = structural_report(
        isogeny_prime_bound=frozen_structural["small_rational_isogeny_degrees"][
            "prime_bound"
        ]
    )

    assert replay["frobenius"] == frozen_structural["frobenius"]
    assert replay["endomorphism_orders"] == frozen_structural["endomorphism_orders"]
    assert replay["exceptional_structure"] == frozen_structural["exceptional_structure"]
    assert replay["verification"] == frozen_structural["verification"]

    benchmark = frozen_benchmark["results"][0]
    assert benchmark["candidate_id"] == "p256-root"
    assert benchmark["linear_relation_verified"] is True
    assert benchmark["trials"] == len(benchmark["rate_trials"]) == 5
    assert math.isclose(
        benchmark["iterations_per_second"],
        sum(benchmark["rate_trials"]) / len(benchmark["rate_trials"]),
        rel_tol=1e-12,
    )
    low, high = benchmark["rate_95_percent_ci"]
    assert low <= benchmark["iterations_per_second"] <= high

    assert frozen_toy["verified"] is True
    toy = load_candidates(ROOT / "data" / "candidates" / "toy.json")[0]
    toy_replay = solve_toy_log(toy, frozen_toy["secret"])
    assert toy_replay["recovered"] == frozen_toy["recovered"] == 4242
    assert toy_replay["verified"] is True

    print(
        json.dumps(
            {
                "status": "verified",
                "discriminant_is_fundamental": replay["frobenius"][
                    "discriminant_is_fundamental"
                ],
                "prime_factor_certificates_verified": replay["frobenius"][
                    "prime_factor_certificates_verified"
                ],
                "baseline_trials_checked": benchmark["trials"],
                "toy_log_recovered": toy_replay["recovered"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
