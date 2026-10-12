#!/usr/bin/env python3
"""Frozen N131 W<=7 projected-base feasibility sample, not an IC run."""

from __future__ import annotations

import hashlib
import json
import math
import random
import resource
import sys
import time
from pathlib import Path

PARENT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(PARENT))
from enumerate_q1413_projected_x import canonical_rotation, projected_x  # noqa: E402
from run_probe import ROOT, curves, field, sha  # noqa: E402

sys.path.insert(0, str(ROOT / "experiments/koblitz-pair-claw-20260929"))
from orbit_key import OrbitKey  # noqa: E402

N = 131
WEIGHT = 7
BASE = PARENT / "runs/n131_q1413_projected_x_w6.json"
PROTOCOL = HERE / "protocol.json"
OUTPUT = HERE / "sample.json"


def wilson(successes: int, trials: int, z: float = 1.959963984540054):
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials +
                         z * z / (4 * trials * trials)) / denominator
    return centre - half, centre + half


def sampled_orbits(onb, orbit, sample_size: int, seed: int):
    """Uniform distinct W7 Frobenius orbits; every orbit has length 131."""
    rng = random.Random(seed)
    seen = set()
    while len(seen) < sample_size:
        coords = sum(1 << i for i in rng.sample(range(N), WEIGHT))
        x = onb.fromCoords(coords)
        orbit_key = canonical_rotation(orbit.cycle_bits(x), N)
        if orbit_key in seen:
            continue
        seen.add(orbit_key)
        yield coords, orbit_key, x


def main():
    assert not OUTPUT.exists(), "refuse to overwrite frozen sample"
    protocol = json.loads(PROTOCOL.read_text())
    base = json.loads(BASE.read_text())
    assert protocol["proposal_id"] == "Q1437"
    assert protocol["candidate_id"] is None and protocol["isogeny"] == "none"
    assert protocol["curve_id"] == base["curve_id"] == "EC1N131Ckb1h6816f880945e"
    assert protocol["source_sha256"] == sha(Path(__file__))
    assert protocol["exact_w6_base_receipt_sha256"] == sha(BASE)
    assert protocol["sample_size"] <= math.comb(N, WEIGHT) // N
    runtime = HERE / "sage_runtime_info.json"
    assert protocol["runtime_info_sha256"] == sha(runtime)
    assert json.loads(runtime.read_text())["status"] == "verified"
    for name, path in protocol["dependencies"].items():
        assert name == str(path["relative_path"])
        assert path["sha256"] == sha(ROOT / name)
    assert curves.curveOrder(N) == 4 * protocol["subgroup_order"]

    onb = field.Onb(N)
    orbit = OrbitKey(onb)
    start = time.perf_counter()
    digest = hashlib.sha256()
    projected_keys = set()
    controls = []
    rational = nonidentity = duplicate_projected = 0
    for coords, raw_key, x in sampled_orbits(
            onb, orbit, protocol["sample_size"], protocol["seed"]):
        is_rational, projected = projected_x(onb, x)
        rational += int(is_rational)
        projected_key = None
        if projected is not None:
            nonidentity += 1
            projected_key = canonical_rotation(orbit.cycle_bits(projected), N)
            if projected_key in projected_keys:
                duplicate_projected += 1
            else:
                projected_keys.add(projected_key)
        digest.update(raw_key.to_bytes(17, "little"))
        digest.update(bytes((int(is_rational), projected is not None)))
        if projected_key is not None:
            digest.update(projected_key.to_bytes(17, "little"))
        if len(controls) < protocol["independent_control_count"]:
            controls.append({"normal_x_mask": coords, "raw_orbit_key": raw_key,
                             "rational": is_rational,
                             "projected_orbit_key": projected_key})

    population_masks = math.comb(N, WEIGHT)
    population_orbits = population_masks // N
    assert population_masks % N == 0
    low, high = wilson(rational, protocol["sample_size"])
    rate = rational / protocol["sample_size"]
    b6 = base["actual_usable_points_B_before_folding"]
    k6 = base["signed_frobenius_columns_K"]
    assert b6 == 2 * N * k6

    def derived(p):
        k = k6 + population_orbits * p
        b = 2 * N * k
        mean = b * (b - 1) * (b - 2) * (b - 3) / (24 * protocol["subgroup_order"])
        return {"conditional_B": b, "conditional_K": k,
                "mean_unordered_distinct_four_subsets_per_uniform_target": mean,
                "optimistic_four_nonzeros_times_K_squared_log2": math.log2(4 * k * k)}

    receipt = {
        "kind": "q1437_n131_weight7_projected_base_feasibility_sample",
        "proposal_id": "Q1437", "candidate_id": None,
        "workload_id": None, "run_id": None,
        "curve_id": protocol["curve_id"], "isogeny": "none",
        "field_degree_n": N, "normal_basis_weight_bound": WEIGHT,
        "sample_law": "uniform distinct W7 Frobenius x-orbits, seeded rejection sampling",
        "sample_size": protocol["sample_size"], "seed": protocol["seed"],
        "population_weight7_x_masks": population_masks,
        "population_weight7_x_orbits": population_orbits,
        "rational_x_orbits_in_sample": rational,
        "nonidentity_projections_in_sample": nonidentity,
        "duplicate_projected_x_orbits_in_sample": duplicate_projected,
        "sample_digest_sha256": digest.hexdigest(),
        "independent_group_controls": controls,
        "sample_rational_rate": rate,
        "sample_wilson_95_interval": [low, high],
        "conditional_estimate": derived(rate),
        "conditional_wilson_interval_endpoints": [derived(low), derived(high)],
        "conditional_assumptions": (
            "W7 rational orbit rate is represented by the frozen sample; "
            "every new rational W7 orbit has nonidentity projection distinct "
            "from all W<=6 and other W7 projected orbits; signed Frobenius "
            "orbits have length 262. Matrix proxy assumes four nonzeros per "
            "row and K sparse-matvec iterations in one logical row-action "
            "unit, with no modular arithmetic, matrix construction, "
            "collection, descent, or verification charge."),
        "actual_usable_points_B_before_folding": None,
        "actual_signed_frobenius_columns_K": None,
        "enumerated_set_sha256": None,
        "ordinary_query_relations": None,
        "complete_solve_work_log2": None,
        "is_empirical_relation_yield": False,
        "is_complete_solve_projection": False,
        "sample_wall_seconds": time.perf_counter() - start,
        "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_units": "bytes on Darwin, KiB on Linux",
        "protocol_sha256": sha(PROTOCOL),
        "runtime_info_sha256": sha(runtime),
        "source_sha256": sha(Path(__file__)),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"rational": rational, "sample_size": protocol["sample_size"],
                      "K_estimate": receipt["conditional_estimate"]["conditional_K"],
                      "matrix_proxy_log2": receipt["conditional_estimate"][
                          "optimistic_four_nonzeros_times_K_squared_log2"]}), flush=True)


if __name__ == "__main__":
    main()
