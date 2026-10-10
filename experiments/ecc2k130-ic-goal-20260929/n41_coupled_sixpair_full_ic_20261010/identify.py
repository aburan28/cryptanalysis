#!/usr/bin/env python3
"""Issue canonical N41 candidate and one-target workload identities."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
HELPER = GOAL / "n131_w18_four_pairs/native_join/frozen_source/helper.cpp"
R = 549756390943


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open("x") as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write("\n")


def main():
    workload = json.loads((HERE / "workload.json").read_text())
    factor_audit = json.loads((HERE / "sage_audit.json").read_text())
    ic_audit = json.loads((HERE / "online_sage_audit.json").read_text())
    rho_audit = json.loads((HERE / "rho_sage_audit.json").read_text())
    fresh_protocol = json.loads((HERE / "fresh/protocol.json").read_text())
    fresh_fixture = json.loads((HERE / "fresh/fixture.json").read_text())
    fresh_audit = json.loads((HERE / "fresh/sage_audit.json").read_text())
    assert factor_audit["status"] == "PASS_INDEPENDENT_SAGE_N41_FACTOR_LOGS_AND_26_RELATIONS"
    assert ic_audit["status"] == "PASS_INDEPENDENT_SAGE_WARM_ONE_TARGET_DLP"
    assert rho_audit["status"] == "PASS_INDEPENDENT_SAGE_SAME_POINT_RHO"
    assert ic_audit["target"] == rho_audit["target"] == workload["public_target_q"]
    assert ic_audit["recovered_scalar"] == rho_audit["recovered_scalar"]
    assert fresh_audit["status"] == "PASS_FRESH_ONE_TARGET_IC_AND_RHO_INDEPENDENT_SAGE"
    assert fresh_audit["target"] == fresh_protocol["target"] == fresh_fixture["target"]
    atoms = workload["atoms"]
    points = sorted({tuple(atom["point"]) for atom in atoms})
    assert len(atoms) == len(points) == workload["actual_factor_base_points_B"] == 384
    assert workload["folded_columns_K"] == 26
    field = {"p": 2, "n": 41, "basis": "polynomial",
             "defining_polynomial_int": 2199023255561,
             "element_encoding": "nonnegative little-endian polynomial coefficient bit mask"}
    curve = {"G": workload["generator"], "coefficients": {
                 "a1": 1, "a2": 0, "a3": 0, "a4": 0, "a6": 1},
             "cofactor": 4, "curve_order": 4 * R,
             "model": "y^2+x*y=x^3+1", "r": R,
             "target_group": "prime_order_r_subgroup", "trace": (1 << 41) + 1 - 4 * R}
    curve_id = "EC1N41Ckb1h" + digest({"field": field, "curve": curve})[:12]
    assert curve_id == "EC1N41Ckb1h023d9a38bbf7"
    curve["curve_id"] = curve_id
    src = {name: sha(path) for name, path in {
        "collector_python": HERE / "collect.py",
        "collection_join_cpp": HERE / "join.cpp", "collection_join_binary": HERE / "join",
        "native_curve_helper_cpp": HELPER, "factor_log_audit_sage": HERE / "audit.py",
        "warm_worker_cpp": HERE / "online_worker.cpp",
        "warm_worker_binary": HERE / "online_worker",
        "warm_input_preparer_python": HERE / "prepare_online.py",
        "warm_runner_python": HERE / "online_run.py",
        "online_audit_sage": HERE / "audit_online.py",
        "supplemental_replay_sage": HERE / "supplemental_replay.py",
        "fresh_runner_python": HERE / "fresh/run.py",
        "fresh_online_audit_sage": HERE / "fresh/audit.py",
    }.items()}
    identity = {
        "schema_version": 1, "field": field, "curve": curve,
        "isogeny": "none",
        "endomorphism": {"endomorphism_order_conductor": None,
                         "frobenius_order_conductor": None,
                         "volcano_levels": None, "status": "unproved_not_used"},
        "factor_base": {
            "construction": "six W6 polynomial-subspace rotation blocks at exponents 0,5,10,15,20,25; each has 64 subgroup-usable signed points",
            "nominal_subspace_dimension": 6,
            "geometric_point_count": len(points),
            "actual_usable_points_B": len(points),
            "enumerated_point_set_sha256": digest([list(point) for point in points]),
            "atom_record_sha256": digest(atoms),
            "representatives": workload["representatives"],
            "effective_columns": 26,
            "subgroup_filter": "all 384 distinct nonidentity points checked for order r",
            "orbit_quotient": "signed Frobenius on prime-order subgroup; lambda=256851699273",
        },
        "point_decomposition": {
            "m": 12, "solver_family": "mitm",
            "summation_chain": "six two-atom pair lists; first two pairs make the indexed four-atom left sum; last four pairs form two equal-seed four-atom domains; sample their product and match the target group sum",
            "equation_order": "exact binary-curve group addition",
            "monomial_order": "none", "internal_matrix_kernel": "none",
            "cache_policy": "reusable left four-atom index and two right four-atom lists",
            "target_probe_cap": 20000000, "target_wall_cap_seconds": 20,
            "implementation": "native_cpp17_arm64",
            "source_sha256": src["warm_worker_cpp"],
        },
        "relation_collection": {
            "collector": "sample", "query_distribution": "distinct nonzero SHA-256-derived known-scalar subgroup setup targets, reduced modulo r",
            "filtering": "twelve distinct signed-Frobenius columns, equal pair-mask seeds in both right quadruples, exact group replay",
            "duplicate_handling": "retain every attempt and insert only rank-novel rows modulo r",
            "stop": "full_rank_26_or_frozen_query_list_exhausted",
            "source_sha256": src["collector_python"],
        },
        "relation_linear_algebra": {
            "modulus": R, "columns": 26,
            "rows": "signed-Frobenius orbit coefficients with known setup scalars as RHS",
            "rank_criterion": "full_rank_26",
            "solver": "gauss", "implementation": "Python_exact_modular_incremental_elimination",
            "block_parameters": "none", "preconditioner": "none",
            "source_sha256": src["collector_python"],
        },
        "target_descent": {
            "policy": "direct twelve-point relation then prepared factor-log sum",
            "recursive_solvers": "none",
            "success": "exact group relation and scalar multiplication replay",
            "source_sha256": src["warm_worker_cpp"],
        },
        "implementation": {
            "compiler": "Apple clang arm64 C++17",
            "algorithm_flags": ["-std=c++17", "-O3", "-DNDEBUG"],
            "source_and_binary_sha256": src,
        },
    }
    candidate_id = "IC1N41Ckb1fb384PDP12mitmRCsampleLAgaussTDdirectISO0h" + digest(identity)[:12]
    save(HERE / "candidate_manifest.json", {
        "candidate_id": candidate_id, "identity_record": identity,
        "prior_curve_id_alias_in_frozen_stage_receipts": workload["curve_id"],
        "identity_sha256": digest(identity),
    })
    workload_identity = {
        "curve_id": curve_id, "subgroup_order": R,
        "generator": workload["generator"], "targets": [workload["public_target_q"]],
        "target_count": 1,
        "target_input_law": "one Python random.Random(202609291700) uniform scalar in [1,r), public point supplied without scalar",
        "target_generation_seed": 202609291700,
        "cache_state": "reusable factor base, four-atom index, constrained right domains, and verified factor logs ready",
        "resource_envelope": {"ic_workers": 1, "rho_workers": 1,
                              "peak_rss_bytes": 4 * 1024**3},
    }
    workload_id = digest(workload_identity)[:12]
    save(HERE / "canonical_workload.json", {
        "curve_id": curve_id, "workload_id": workload_id,
        "identity_record": workload_identity,
        "identity_sha256": digest(workload_identity),
        "prior_curve_id_alias_in_frozen_stage_receipts": workload["curve_id"],
    })
    fresh_identity = {
        "curve_id": curve_id, "subgroup_order": R,
        "generator": workload["generator"], "targets": [fresh_protocol["target"]],
        "target_count": 1,
        "target_input_law": "one independent SHA-256-derived scalar reduced modulo r, public point supplied without scalar",
        "target_generation_seed": fresh_fixture["seed"],
        "cache_state": "reusable factor base, four-atom index, constrained right domains, and verified factor logs ready",
        "resource_envelope": {"ic_workers": 1, "rho_workers": 1,
                              "peak_rss_bytes": 4 * 1024**3},
    }
    fresh_id = digest(fresh_identity)[:12]
    save(HERE / "fresh/canonical_workload.json", {
        "curve_id": curve_id, "workload_id": fresh_id,
        "identity_record": fresh_identity,
        "identity_sha256": digest(fresh_identity),
        "prior_curve_id_alias_in_frozen_stage_receipts": workload["curve_id"],
    })
    print(json.dumps({"candidate_id": candidate_id, "workload_id": workload_id,
                      "run_id": f"{candidate_id}W{workload_id}R1",
                      "fresh_workload_id": fresh_id,
                      "fresh_run_id": f"{candidate_id}W{fresh_id}R1"}))


if __name__ == "__main__":
    main()
