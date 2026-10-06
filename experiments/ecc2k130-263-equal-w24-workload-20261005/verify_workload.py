#!/usr/bin/env sage -python
"""Independently replay W24 mask streams, route, controls and public fixtures."""

import argparse
import gzip
import hashlib
import json
import resource
import struct
import sys
import time
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing, ZZ


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1"
ROUTE = ROOT / "experiments/koblitz-polynomial-w-pair-20260925/ecc2k130_degree263_route_manifest.json"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def full_mask_replay(name, row, config):
    path = ARCHIVE / f"{name}-masks.bin.gz"
    assert digest(path) == config[f"{name}_masks_gzip_sha256"]
    h = hashlib.sha256()
    selected = hashlib.sha256()
    selected_size = config["selected_signed_columns_each"]
    control_set = set(row["control_indices_selection_order"])
    found = {}
    prior = 0
    position = 0
    last = None
    excluded = None
    with gzip.open(path, "rb") as stream:
        while data := stream.read(1 << 20):
            assert len(data) % 4 == 0
            h.update(data)
            for (mask,) in struct.iter_unpack("<I", data):
                assert prior < mask < (1 << 24)
                if position < selected_size:
                    selected.update(struct.pack("<I", mask))
                    last = mask
                elif position == selected_size:
                    excluded = mask
                if position in control_set:
                    found[position] = mask
                prior = mask
                position += 1
    assert position == config[f"{name}_full_signed_columns"]
    assert h.hexdigest() == config[f"{name}_masks_raw_sha256"]
    assert selected.hexdigest() == row["selected_mask_stream_sha256"]
    assert last == row["last_selected_mask"]
    assert excluded == row["first_excluded_mask"]
    assert [found[i] for i in row["control_indices_selection_order"]] == row[
        "control_masks_selection_order"]
    assert row["selected_usable_points_B"] == 2*selected_size
    return {"full_mask_count": position, "selected_count": selected_size,
            "selected_sha256": selected.hexdigest(), "last_selected": last}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE / "verification.json")
    args = parser.parse_args()
    assert not args.out.exists()
    started = time.perf_counter()
    config = json.loads((HERE / "CONFIG.json").read_text())
    base = json.loads((HERE / "base_selection.json").read_text())
    workload = json.loads((HERE / "workload.json").read_text())
    fixtures = json.loads((HERE / "target_fixtures.json").read_text())
    controls = json.loads((HERE / "point_controls.json").read_text())
    producer = json.loads((HERE / "producer_receipt.json").read_text())
    route = json.loads(ROUTE.read_text())
    assert config["route_manifest_sha256"] == digest(ROUTE)
    assert base["config_sha256"] == digest(HERE / "CONFIG.json")
    assert workload["config_sha256"] == base["config_sha256"]
    assert workload["base_selection_sha256"] == digest(HERE / "base_selection.json")
    assert controls["base_selection_sha256"] == workload["base_selection_sha256"]
    assert producer["sage_runtime_info_sha256"] == digest(HERE / "runtime-info.json")
    assert (HERE / "runtime-info-verifier.json").is_file()
    assert producer["producer_sha256"] == digest(HERE / "freeze_workload.py")
    assert base["producer_sha256"] == digest(HERE / "freeze_base.py")
    assert producer["status"] == "PASS_INPUT_CONSTRUCTION_UNVERIFIED"
    assert workload["source_curve_id"] == route["curve_nodes"]["source"]["curve_id"]
    assert workload["descendant_curve_id"] == route["curve_nodes"]["target"]["curve_id"]
    assert workload["route_id"] == route["route_id"]
    assert workload["primary_target_index"] == 0
    assert workload["remaining_targets_status"] == "dormant_fixture_controls"
    assert workload["target_count"] == config["target_count"] == len(workload["targets"])
    assert len(fixtures["accepted_scalars"]) == len(workload["targets"])
    assert len(controls["source"]) == len(controls["descendant_native"]) == 64
    identity = dict(workload)
    claimed_id = identity.pop("workload_id")
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    full_identity = hashlib.sha256(canonical).hexdigest()
    assert claimed_id == full_identity[:12] == fixtures["workload_id"]
    assert fixtures["workload_identity_sha256"] == full_identity
    mask_results = {
        "source": full_mask_replay("source", base["source"], config),
        "descendant": full_mask_replay("descendant", base["descendant_native"], config),
    }
    print("mask streams replayed", mask_results, flush=True)

    binary = PolynomialRing(GF(2), "z")
    z = binary.gen()
    modulus = z**131 + z**13 + z**2 + z + 1
    assert modulus.is_irreducible()
    k = GF(2**131, "z", modulus=modulus)

    def decode(number):
        number = int(number)
        return k(sum(z**j for j in range(number.bit_length())
                     if (number >> j) & 1))

    def encoded(element):
        return sum(int(bit) << j for j, bit in enumerate(element.polynomial().list()))

    def decode_point(curve, words):
        assert len(words) == 2 and all(isinstance(v, int) for v in words)
        point = curve([decode(words[0]), decode(words[1])])
        assert [encoded(point[0]), encoded(point[1])] == words
        return point

    source = EllipticCurve(k, [1, 0, 0, 0, 1])
    ring = PolynomialRing(k, "Y")
    forward_polynomial = ring([decode(c) for c in route["isogeny"][
        "forward_map"]["kernel_polynomial_coefficients"]])
    reverse_polynomial = ring([decode(c) for c in route["isogeny"][
        "dual_map"]["kernel_polynomial_coefficients"]])
    forward = source.isogeny(forward_polynomial, check=True)
    descendant = forward.codomain()
    assert [encoded(a) for a in descendant.ainvs()] == route["curve_nodes"][
        "target"]["coefficients_a1_a2_a3_a4_a6"]
    reverse = descendant.isogeny(reverse_polynomial, check=True)
    iso = reverse.codomain().isomorphism_to(source)
    orientation = ZZ(route["isogeny"]["dual_map"]["composition_sign"])
    assert [encoded(a) for a in iso.tuple()] == route["isogeny"][
        "dual_map"]["isomorphism_tuple_to_source"]
    r = ZZ(route["curve_nodes"]["source"]["subgroup_order"])
    inv = ZZ(263).inverse_mod(r)
    G = decode_point(source, route["curve_nodes"]["source"]["generator_G"])
    H = decode_point(descendant, route["curve_nodes"]["target"]["generator_G"])
    assert forward(G) == H and orientation*iso(reverse(H)) == 263*G
    assert inv*orientation*iso(reverse(H)) == G
    A = decode(route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"][3])
    b = decode(route["curve_nodes"]["target"][
        "coefficients_a1_a2_a3_a4_a6"][4]) + A*A
    normalized = EllipticCurve(k, [1, 0, 0, 0, b])
    alpha = b**(1 << 129)
    assert alpha**4 == b
    basis = [k.gen()**j + (k.gen()**j).trace()
             for j in range(1, config["w_dimension"] + 1)]

    def halftrace(value):
        assert value.trace() == 0
        answer = k.zero()
        power = value
        for _ in range(66):
            answer += power
            power = power**4
        assert answer*answer + answer == value
        return answer

    def base_point(mask, curve, fourth_root, c):
        w = sum((basis[j] for j in range(24) if mask & (1 << j)), k.zero())
        assert w and w.trace() == 0
        u = halftrace(w)
        x = fourth_root*(1 + 1/u)
        rhs = x + c/(x*x)
        point = curve([x, x*halftrace(rhs)])
        projected = 4*point
        assert not projected.is_zero() and r*projected == curve(0)
        return projected

    for name, data in (("source", controls["source"]),
                       ("descendant_native", controls["descendant_native"])):
        row = base[name]
        assert [item["index"] for item in data] == row["control_indices_selection_order"]
        assert [item["mask"] for item in data] == row["control_masks_selection_order"]
        for item in data:
            if name == "source":
                point = base_point(item["mask"], source, k.one(), k.one())
                assert point == decode_point(source, item["source"])
                image = decode_point(descendant, item["transported"])
                assert forward(point) == image
                assert inv*orientation*iso(reverse(image)) == point
            else:
                temporary = base_point(item["mask"], normalized, alpha, b)
                native = descendant([temporary[0], temporary[1] + A])
                assert native == decode_point(descendant, item["descendant_native"])
                pulled = decode_point(source, item["pullback"])
                assert pulled == inv*orientation*iso(reverse(native))
                assert forward(pulled) == native
    print("all sampled base controls replayed", flush=True)

    accepted = set()
    counter = 0
    for index, (entry, given) in enumerate(zip(workload["targets"],
                                               fixtures["accepted_scalars"])):
        while True:
            payload = (config["target_scalar_domain"].encode() + b":" +
                       counter.to_bytes(8, "big"))
            value = int.from_bytes(hashlib.sha256(payload).digest()[:17],
                                   "big") & ((1 << 130) - 1)
            current = counter
            counter += 1
            if 0 < value < r and value not in accepted:
                accepted.add(value)
                break
        assert int(given) == value
        assert entry["index"] == index and entry["counter"] == current
        source_point = decode_point(source, entry["source"])
        descendant_point = decode_point(descendant, entry["descendant"])
        assert source_point == ZZ(value)*G
        assert descendant_point == ZZ(value)*H == forward(source_point)
        assert inv*orientation*iso(reverse(descendant_point)) == source_point
        if (index + 1) % 64 == 0:
            print("target fixtures replayed", index + 1, flush=True)
    assert fixtures["counter_attempts"] == counter
    elapsed = time.perf_counter() - started
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == "darwin" else peak*1024
    assert elapsed <= config["wall_limit_seconds"]
    assert peak <= config["peak_rss_limit_bytes"]
    result = {"schema": "ecc2k130-263-equal-w24-verification-v1",
              "status": "PASS_EXACT_BASE_ROUTE_AND_PUBLIC_FIXTURES",
              "verified": True, "candidate_id": None, "workload_id": claimed_id,
              "workload_identity_sha256": full_identity,
              "independent_mask_replay": mask_results,
              "source_control_count": len(controls["source"]),
              "native_control_count": len(controls["descendant_native"]),
              "fixture_count": len(workload["targets"]),
              "control_sha256": digest(HERE / "point_controls.json"),
              "public_workload_sha256": digest(HERE / "workload.json"),
              "fixture_sha256": digest(HERE / "target_fixtures.json"),
              "producer_receipt_sha256": digest(HERE / "producer_receipt.json"),
              "verifier_sha256": digest(Path(__file__)),
              "runtime_info_sha256": digest(HERE / "runtime-info.json"),
              "verifier_runtime_info_sha256": digest(HERE / "runtime-info-verifier.json"),
              "wall_seconds": elapsed, "peak_rss_bytes": peak,
              "natural_pdp_yield": None, "verified_relation_rank": None,
              "verified_logarithm": None, "online_wall_time": None,
              "rho_ratio": None}
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"status": result["status"], "workload_id": claimed_id,
                      "wall_seconds": round(elapsed, 3)}), flush=True)


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("assertions must remain enabled")
    main()
