#!/usr/bin/env python3
"""Read-only independent arithmetic and contract replay of the complete N13 receipt."""

from __future__ import annotations

from itertools import combinations_with_replacement
import json
from pathlib import Path
import random
import statistics

import complete_n13_sat as run
import analyze


HERE = Path(__file__).resolve().parent


def reference_sum(points, modulus):
    total = None
    for point in points:
        total = run.E.ref.add(total, point, 13, modulus)
    return total


def reference_mul(point, scalar, modulus):
    return run.E.ref.scalar_mul(point, scalar, 13, modulus)


def main():
    receipt = json.loads((HERE / "complete_n13_sat_receipt.json").read_text())
    manifest = json.loads((HERE / "complete_n13_sat_candidate.json").read_text())
    runs = [json.loads(line) for line in (HERE / "complete_n13_sat_runs.jsonl").read_text().splitlines()]
    record = manifest["record"]
    candidate_id = "IC1N13Ckb1fb6PDP4satRCsampleLAgaussTDdescentISO0h" + run.digest(record)[:12]
    assert candidate_id == manifest["candidate_id"] == receipt["candidate_id"]
    assert receipt["candidate_manifest_sha256"] == run.digest(record)
    assert receipt["source_sha256"] == run.file_sha(HERE / "complete_n13_sat.py")
    for relative, expected in record["implementation"]["source_sha256"].items():
        assert run.file_sha(run.ROOT / relative) == expected
    import pycryptosat
    assert run.file_sha(Path(pycryptosat.__file__)) == record["point_decomposition"]["native_binary_sha256"]
    field = record["field"]
    modulus = field["defining_polynomial_int"]
    curve = dict(record["curve"])
    curve_id = curve.pop("curve_id")
    assert curve_id == "EC1N13Ckb1h" + run.digest({"field": field, "curve": curve})[:12]
    assert field["n"] == 13 and modulus == 0x201b and curve["r"] == run.R
    generator = tuple(curve["G"])
    base = [tuple(point) for point in record["factor_base"]["encoded_points"]]
    assert len(base) == 6 and len(set(base)) == 6
    assert run.digest([list(point) for point in base]) == record["factor_base"]["point_set_sha256"]
    # Independently enumerate the full point-sum support using the slow
    # reference arithmetic, not the SAT index or measured curve operations.
    support = {reference_sum((base[i] for i in indices), modulus)
               for indices in combinations_with_replacement(range(6), 4)}
    assert len(support - {None}) == 84
    assert receipt["cold_preparation"]["sumset_support_nonidentity"] == 84
    assert receipt["cold_preparation"]["sumset_tuple_count"] == 126

    # Folded representatives and coefficients come from the exact base recipe;
    # the saved relations and logs are then checked via reference arithmetic.
    context = run.prepare()
    reps = context["reps"]
    prep = receipt["cold_preparation"]["factor_log_collection"]
    assert receipt["cold_preparation"]["relation_query_seed"] == 61013
    logs = prep["logs"]
    assert prep["rank"] == len(reps) == len(logs) == 2
    assert prep["novel_rows"] == 2 and len(prep["records"]) == 39
    for representative, log in zip(reps, logs):
        assert reference_mul(representative, run.R, modulus) is None
        assert reference_mul(generator, log, modulus) == representative
    precomputed_targets = set()
    for item in prep["records"]:
        assert item["pdp_wall_ns"] >= item["native_solver_wall_ns"]
        target = tuple(item["target"])
        precomputed_targets.add(target)
        assert reference_mul(generator, item["known_query_scalar"], modulus) == target
        assert (item["status"] == "verified") == (target in support)
        if item["witness"] is not None:
            assert reference_sum((base[i] for i in item["witness"]), modulus) == target
            row_point = reference_sum((reference_mul(rep, coefficient, modulus)
                                       for rep, coefficient in zip(reps, item["row"])), modulus)
            assert row_point == target
    assert len(receipt["targets"]) == len(runs) == 20
    seen_targets = set()
    for item, saved in zip(receipt["targets"], runs):
        assert saved["provenance"]["relation_precompute_seed"] == 61013
        assert saved["provenance"]["target_descent_seed"] == item["target_descent_seed"]
        assert saved["provenance"]["rho_walk_seed"] == item["rho_walk_seed"]
        target = tuple(item["fixture"]["target"])
        assert target not in precomputed_targets and target not in seen_targets
        seen_targets.add(target)
        scalar = item["audit_fixture_scalar"]
        assert reference_mul(generator, scalar, modulus) == target
        assert item["ic"]["scalar"] == item["rho"]["scalar"] == scalar
        fixture_hash = run.digest(item["fixture"])
        assert item["workload"] == {"fixture_sha256": fixture_hash,
                                    "workload_id": "W" + fixture_hash[:12]}
        assert saved["candidate_id"] == candidate_id
        assert saved["run_id"] == item["run_id"]
        assert saved["workload_id"] == item["workload"]["workload_id"]
        assert saved["target_point_sha256"] == run.digest(list(target))
        assert saved["online_wall_ns"] == item["ic"]["wall_ns"]
        assert saved["rho_online_wall_ns"] == item["rho"]["wall_ns"]
        assert sum(item["ic"]["online_phase_wall_ns"].values()) == item["ic"]["wall_ns"]
        assert item["online_speedup"] == item["rho"]["wall_ns"] / item["ic"]["wall_ns"]
        assert len(item["ic"]["trace"]) == item["ic"]["attempts"]
        for attempt in item["ic"]["trace"]:
            translated = None if attempt["translated"] is None else tuple(attempt["translated"])
            if translated is None:
                assert attempt["status"] == "identity_translation"
            else:
                assert (attempt["status"] == "verified") == (translated in support)
        translated = reference_sum((target, reference_mul(generator, item["ic"]["last_shift"], modulus)), modulus)
        assert translated == tuple(item["ic"]["trace"][-1]["translated"])
        assert reference_sum((base[i] for i in item["ic"]["last_witness"]), modulus) == translated
        row_point = reference_sum((reference_mul(rep, coefficient, modulus)
                                   for rep, coefficient in zip(reps, item["ic"]["last_row"])), modulus)
        assert row_point == translated
        assert (sum(c * log for c, log in zip(item["ic"]["last_row"], logs))
                - item["ic"]["last_shift"]) % run.R == scalar
        analyze.validate_run(saved)
    ratios = [item["online_speedup"] for item in receipt["targets"]]
    bootstrap_rng = random.Random(98103)
    bootstrap = sorted(statistics.median(ratios[bootstrap_rng.randrange(len(ratios))]
                                         for _ in ratios) for _ in range(10000))
    print(f"verified {len(runs)} paired single-target DLP runs for {candidate_id}")
    print(f"first rho/IC={ratios[0]:.6f}; paired median={statistics.median(ratios):.6f}; "
          f"bootstrap95=[{bootstrap[250]:.6f}, {bootstrap[9750]:.6f}]")


if __name__ == "__main__":
    main()
