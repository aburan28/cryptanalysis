#!/usr/bin/env python3
"""Independently verify the complete n=53 known-log quotient-table DLP."""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODEGEN = HERE.parents[1] / "ecc2k130" / "runner" / "codegen"
sys.path.insert(0, str(CODEGEN))

import curves
import field
from bench_n83_full_base import CompactOrbitBase
from orbit_key import OrbitKey
from run_n23 import frozen, sha


def verify():
    run = json.loads((HERE / "runs" / "n53_knownlog_one_target.json").read_text())
    candidate_id = run["candidate_id"]
    candidate = json.loads((HERE / "candidates" /
                            f"{candidate_id}.json").read_text())
    record = {key: value for key, value in candidate.items()
              if key not in ("candidate_id", "candidate_record_sha256")}
    candidate_hash = hashlib.sha256(frozen(record)).hexdigest()
    assert candidate_hash == candidate["candidate_record_sha256"] == run[
        "candidate_record_sha256"]
    assert candidate_id == ("IC1N53Ckb1fb24062PDP4qtableRCdirectLAnoneTDdirect"
                            f"ISO0h{candidate_hash[:12]}")
    assert run["source_sha256"] == sha(HERE / "knownlog_n53.py")
    for name, digest in candidate["implementation"]["source_sha256"].items():
        assert digest == sha(HERE / name)
    for name, digest in run["dependency_sha256"].items():
        assert digest == sha(CODEGEN / name)
    assert run["workload_id"] == hashlib.sha256(frozen(
        run["workload"])).hexdigest()[:12]
    assert run["run_id"] == f"{candidate_id}W{run['workload_id']}R1"
    reference_path = (HERE.parent / "ecc2k130-quotient-pair-probe-20260926" /
                      "runs" / "n53_perf_prefix.json")
    assert run["reference_sha256"] == sha(reference_path)
    reference = json.loads(reference_path.read_text())
    identity = run["curve_identity_record"]
    curve_id = "EC1N53Ckb1h" + hashlib.sha256(frozen(identity)).hexdigest()[:12]
    assert run["curve_id"] == reference["curve_id"] == curve_id
    assert candidate["field"] == identity["field"]
    assert candidate["curve"] == dict(identity["curve"], curve_id=curve_id)
    assert candidate["isogeny"] == run["isogeny"] == "none"
    assert candidate["relation_linear_algebra"] == "none"
    order = identity["curve"]["subgroup_order"]
    assert curves.isPrimeBig(order)
    onb = field.Onb(53)
    curve = curves.Curve(onb)
    orbit = OrbitKey(onb)
    generator = tuple(identity["curve"]["generator"])
    target = tuple(run["workload"]["target"])
    assert target == tuple(reference["workload"]["target"])
    assert curve.mul(generator, order) is None
    assert curve.mul(target, order) is None
    base_record = candidate["factor_base"]
    assert base_record == run["factor_base"]
    eigen = base_record["frobenius_eigenvalue_mod_r"]
    assert curve.mul(generator, eigen) == curve.frob(generator)
    assert pow(eigen, 53, order) == 1 and eigen != 1
    entries = {}
    for alpha in base_record["seed_scalars_in_draw_order"]:
        point = curve.mul(generator, alpha)
        key, exponent, sign = orbit.canonical(point)
        entries.setdefault(key, sign * pow(eigen, exponent, order) * alpha % order)
    keys = sorted(entries)
    logs = [entries[key] for key in keys]
    assert len(keys) == base_record["selected_point_orbits"] == 227
    assert [str(key) for key in keys] == base_record["canonical_orbit_keys"]
    assert logs == base_record["canonical_logs"]
    assert hashlib.sha256(b"".join(key.to_bytes(14, "little")
                                for key in keys)).hexdigest() == base_record[
                                    "enumerated_set_sha256"]
    assert hashlib.sha256(b"".join(log.to_bytes(6, "little")
                                for log in logs)).hexdigest() == base_record[
                                    "canonical_log_sha256"]
    assert all(curve.mul(generator, log) == orbit.point_from_key(key)
               for key, log in zip(keys, logs))
    base = CompactOrbitBase(orbit, keys)
    assert len(base) == base_record["actual_usable_points_B_before_folding"] == 24062
    assert base_record["signed_frobenius_columns"] == 227

    relation = run["relation"]
    zero, one = relation["zero_meta"], relation["one_meta"]
    zero_pair = curve.add(base[zero[0]], base[zero[1]])
    one_pair = curve.add(base[one[0]], base[one[1]])
    complement = curve.add(target, curve.neg(one_pair))
    zero_key, zero_exp, zero_sign = orbit.canonical(zero_pair)
    one_key, one_exp, one_sign = orbit.canonical(complement)
    assert zero_key == one_key
    assert zero[2:] == [zero_exp, zero_sign]
    assert one[2:] == [one_exp, one_sign]
    shift = (zero_exp - one_exp) % 53
    sign = zero_sign * one_sign
    assert shift == relation["frobenius_shift_of_zero_pair"]
    assert sign == relation["sign_of_zero_pair"]
    points = [curve.frob(base[zero[0]], shift),
              curve.frob(base[zero[1]], shift),
              base[one[0]], base[one[1]]]
    if sign < 0:
        points[:2] = [curve.neg(point) for point in points[:2]]
    assert [list(point) for point in points] == relation["points"]
    assert all(points[i] != curve.neg(points[j])
               for i in range(4) for j in range(i))
    total = None
    for point in points:
        total = curve.add(total, point)
    assert total == target

    powers = [pow(eigen, j, order) for j in range(53)]
    def known_log(index):
        orbit_index, within = divmod(index, 106)
        signed = 1 if within < 53 else -1
        return signed * powers[within % 53] * logs[orbit_index] % order
    scalar = (sign * powers[shift] *
              (known_log(zero[0]) + known_log(zero[1])) +
              known_log(one[0]) + known_log(one[1])) % order
    assert scalar == run["recovered_scalar"]
    assert curve.mul(generator, scalar) == target
    assert scalar == reference["target_fixture_scalar"]
    assert run["verified_single_target_dlp"] is True
    assert run["verified_relation_count"] == 1

    table_rng = random.Random(run["workload"]["table_sample_seed"])
    zero_seen = False
    for _ in range(run["table_samples"]):
        indices = (table_rng.randrange(len(base)),
                   table_rng.randrange(len(base)))
        zero_seen |= indices == tuple(zero[:2])
    assert zero_seen
    query_rng = random.Random(run["workload"]["query_sample_seed"])
    for _ in range(run["target_query_samples_to_relation"]):
        indices = (query_rng.randrange(len(base)),
                   query_rng.randrange(len(base)))
    assert indices == tuple(one[:2])
    assert run["online_one_target_wall_ns"] == sum(
        run["online_phase_wall_ns"].values())
    assert run["cold_total_wall_ns"] == (
        run["target_independent_base_setup_wall_ns"] +
        run["target_independent_table_build_wall_ns"] +
        run["target_independent_membership_index_wall_ns"] +
        run["online_one_target_wall_ns"])
    assert run["logical_pair_samples_cold"] == (
        run["table_samples"] + run["target_query_samples_to_relation"])
    assert run["rho_online_wall_ns"] is None
    assert run["online_speedup"] is None
    return {"curve_id": curve_id, "candidate_id": candidate_id,
            "actual_B": len(base), "columns": len(keys),
            "recovered_scalar": scalar,
            "online_seconds": run["online_one_target_wall_ns"] / 1e9,
            "cold_pair_samples": run["logical_pair_samples_cold"]}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
