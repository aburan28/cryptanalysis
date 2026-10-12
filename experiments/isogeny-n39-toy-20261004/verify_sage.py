#!/usr/bin/env sage -python
"""Independently replay every saved N39 relation and map/base identity."""

import argparse
import hashlib
import json
from pathlib import Path
import random

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=HERE / "receipt-r1.json")
    args = parser.parse_args()
    record = json.loads(args.receipt.read_text())
    protocol = json.loads((HERE / "protocol.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    assert record["status"] == "verified_stage_control"
    assert record["proposal_id"] == protocol["proposal_id"] == "Q1419"
    assert record["candidate_id"] is None
    assert record["source_sha256"] == protocol["source_sha256"] == sha256(HERE / "run.py")
    assert record["runtime_info_sha256"] == protocol["runtime_info_sha256"] == sha256(
        HERE / "runtime-info.json")
    assert record["workload"]["base_size"] == protocol["base_size_actual_usable_points"]
    assert record["workload"]["target_count"] == protocol["target_count"]
    assert record["workload"]["target_seed"] == protocol["target_seed"]
    canonical = json.dumps(workload["workload_record"], sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    assert workload["workload_id"] == hashlib.sha256(canonical).hexdigest()[:12]
    assert workload["workload_record"]["source_targets"] == [
        row["source_target"] for row in record["held_out_rows"]]
    assert workload["workload_record"]["descendant_targets"] == [
        row["descendant_target"] for row in record["held_out_rows"]]

    f2ring = PolynomialRing(GF(2), "t")
    t = f2ring.gen()
    modulus = t**39 + t**4 + 1
    assert modulus.is_irreducible()
    field = GF(2**39, "t", modulus=modulus)

    def decode(value):
        return field(sum(t**index for index in range(value.bit_length())
                         if value & (1 << index)))

    source = EllipticCurve(field, [1, 0, 0, 0, 1])
    ring = PolynomialRing(field, "X")
    forward_kernel = ring([decode(value) for value in record[
        "isogeny"]["forward_kernel_coefficients"]])
    assert any(value not in (0, 1) for value in record[
        "isogeny"]["forward_kernel_coefficients"])
    forward = source.isogeny(forward_kernel, check=True)
    target_curve = forward.codomain()
    assert target_curve.j_invariant() != source.j_invariant()
    assert list(target_curve.ainvs()) == [decode(value) for value in record[
        "descendant_curve"]["ainvs"]]
    dual_kernel = ring([decode(value) for value in record[
        "isogeny"]["dual_kernel_coefficients"]])
    dual = target_curve.isogeny(dual_kernel, check=True)
    iso = dual.codomain().isomorphism_to(source)
    sign = ZZ(record["isogeny"]["dual_composition_sign"])
    inverse = ZZ(record["isogeny"]["ell_inverse_mod_subgroup_order"])
    r = ZZ(record["source_curve"]["subgroup_order"])
    assert sign in (-1, 1) and (79*inverse) % r == 1

    def point(curve, pair):
        return curve([decode(pair[0]), decode(pair[1])])

    bases = {}
    expected_size = protocol["base_size_actual_usable_points"]
    for name in protocol["factor_base_policies"]:
        curve = source if name in ("source", "pullback") else target_curve
        bases[name] = tuple(point(curve, pair) for pair in record[
            "factor_bases"][name]["points"])
        assert len(bases[name]) == expected_size
        assert len(set(bases[name])) == expected_size
        assert all(not item.is_zero() and r*item == curve(0) for item in bases[name])
    for original, mapped in zip(bases["source"], bases["transported"]):
        assert forward(original) == mapped
        assert sign*iso(dual(mapped)) == 79*original
    for original, mapped in zip(bases["pullback"], bases["descendant_native"]):
        assert forward(original) == mapped
        assert inverse*sign*iso(dual(mapped)) == original

    generator = point(source, record["source_curve"]["generator"])
    mapped_generator = point(target_curve, record["descendant_curve"]["generator"])
    assert forward(generator) == mapped_generator
    rng = random.Random(protocol["target_seed"])
    scalars = rng.sample(range(1, int(r)), protocol["target_count"])
    counts = {name: 0 for name in bases}
    source_only = native_only = 0
    pair_count = expected_size*(expected_size+1)//2
    for index, row in enumerate(record["held_out_rows"]):
        assert row["index"] == index and row["fixture_scalar"] == scalars[index]
        source_target = point(source, row["source_target"])
        descendant_target = point(target_curve, row["descendant_target"])
        assert ZZ(scalars[index])*generator == source_target
        assert forward(source_target) == descendant_target
        assert inverse*sign*iso(dual(descendant_target)) == source_target
        hits = {}
        for name, base in bases.items():
            result = row["policies"][name]
            assert 1 <= result["probes"] <= pair_count
            query = source_target if name in ("source", "pullback") else descendant_target
            if result["status"] == "verified_relation":
                witness = result["witness"]
                assert len(witness) == 4
                assert all(0 <= element < expected_size for element in witness)
                assert sum((base[element] for element in witness), query.curve()(0)) == query
                hits[name] = True
                counts[name] += 1
            else:
                assert result["status"] == "no_relation"
                assert result["witness"] is None and result["probes"] == pair_count
                hits[name] = False
        assert hits["source"] == hits["transported"]
        assert hits["descendant_native"] == hits["pullback"]
        source_only += hits["source"] and not hits["descendant_native"]
        native_only += hits["descendant_native"] and not hits["source"]
    assert counts == record["verified_hit_counts"]
    assert source_only == record["paired_source_only"]
    assert native_only == record["paired_native_only"]
    assert record["complete_ic_online_ms"] is None
    assert record["rho_online_ms"] is None and record["speedup"] is None
    analysis = json.loads((HERE / "analysis-r1.json").read_text())
    assert analysis["receipt_sha256"] == sha256(args.receipt)
    assert analysis["workload_id"] == workload["workload_id"]
    assert analysis["workload_sha256"] == sha256(HERE / "workload.json")
    assert analysis["source_verified_hits"] == counts["source"]
    assert analysis["descendant_native_verified_hits"] == counts["descendant_native"]
    assert analysis["source_only_targets"] == source_only
    assert analysis["descendant_native_only_targets"] == native_only
    assert analysis["decision"] == "deprioritize_this_native_base_policy"
    print(json.dumps({"verified": True, "targets": len(scalars),
                      "hit_counts": counts, "source_only": source_only,
                      "native_only": native_only}, indent=2))


if __name__ == "__main__":
    main()
