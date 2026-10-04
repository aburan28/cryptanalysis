#!/usr/bin/env python3
"""Freeze exact curve identities and a verified degree-263 route artifact."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(name):
    path = HERE / name
    return json.loads(path.read_text()), hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    forward, forward_sha = load("ecc2k130_degree263_isogeny_control.json")
    dual, dual_sha = load("ecc2k130_degree263_dual_control.json")
    replay, replay_sha = load("ecc2k130_degree263_isogeny_sage_replay.json")
    exceptional, exceptional_sha = load("ecc2k130_degree263_exceptional_replay.json")
    runtime, runtime_sha = load("ecc2k130_degree263_exceptional_runtime_info.json")
    for report, script in ((forward, "sage_construct_ecc2k130_263_isogeny.py"),
                           (dual, "sage_construct_ecc2k130_263_dual.py"),
                           (replay, "sage_replay_ecc2k130_263_isogeny.py")):
        assert report["source_sha256"] == hashlib.sha256((
            HERE / script).read_bytes()).hexdigest()
    assert replay["input_report_sha256"] == forward_sha
    assert replay["dual_report_sha256"] == dual_sha
    assert replay["cyclic_kernel_check"]
    assert replay["dual_composition_on_two_points"]
    assert replay["source_and_target_subgroup_checks"]
    assert forward["kernel_polynomial_sha256"] == dual["forward_kernel_sha256"]
    assert forward["isogeny_degree"] == 263
    assert forward["codomain_j"] != 1
    assert [value for value in range(263) if (
        value*value + value + 2) % 263 == 0] == [123, 139]
    # A monic kernel with F2-stable roots would have every coefficient in F2.
    assert any(value not in (0, 1) for value in forward[
        "kernel_polynomial_coefficients"])
    assert exceptional["status"] == runtime["status"] == "verified"
    assert exceptional["sage_version"] == runtime["sage_version"]
    assert exceptional["forward_report_sha256"] == forward_sha
    assert exceptional["dual_report_sha256"] == dual_sha
    assert exceptional["source_sha256"] == hashlib.sha256((
        HERE / "sage_verify_ecc2k130_263_exceptional.py").read_bytes()).hexdigest()
    assert exceptional["transport_source_sha256"] == hashlib.sha256((
        HERE / "degree263_transport.py").read_bytes()).hexdigest()
    assert exceptional["forward_nonzero_kernel_points_mapped_to_infinity"] == 262
    assert exceptional["dual_nonzero_kernel_points_mapped_to_infinity"] == 262
    assert exceptional["all_kernel_roots_have_no_base_field_y_lift"]
    assert exceptional["rational_order_two_composition"]
    assert exceptional["ordinary_subgroup_wrapper_and_dual_composition"]
    assert exceptional["ordinary_quadratic_extension_wrapper_agrees"]

    r = int(forward["subgroup_order"])
    q = 2**131
    trace = -22283658519494248867
    assert q + 1 - trace == 4 * r
    field = {
        "p": 2, "n": 131,
        "representation": "polynomial_basis",
        "defining_modulus_low_terms": [0, 1, 2, 13, 131],
        "element_encoding": "little_endian_polynomial_basis_integer",
    }

    def curve(coefficients, generator, tag):
        content = {
            "weierstrass_equation": "y^2+a1*x*y+a3*y=x^3+a2*x^2+a4*x+a6",
            "coefficients_a1_a2_a3_a4_a6": coefficients,
            "curve_order": 4 * r,
            "trace": trace,
            "subgroup_order": r,
            "cofactor": 4,
            "generator_G": generator,
            "target_group": "cyclic_subgroup_generated_by_G",
        }
        identifier = "EC1N131C" + tag + "h" + digest({"field": field,
                                                       "curve": content})[:12]
        return dict(content, curve_id=identifier)

    source = curve([1, 0, 0, 0, 1], forward["source_generator"], "kb1")
    target = curve(forward["codomain_ainvs"],
                   forward["transported_generator"], "bin")
    assert source["curve_id"] != target["curve_id"]

    map_spec = {
        "map_type": "normalized_kohel_isogeny_from_kernel_polynomial",
        "degree": 263,
        "source_curve_id": source["curve_id"],
        "target_curve_id": target["curve_id"],
        "kernel_polynomial_coefficients": forward[
            "kernel_polynomial_coefficients"],
        "construction": "Sage 10.9 EllipticCurve.isogeny(kernel,check=True)",
    }
    dual_spec = {
        "map_type": "kohel_isogeny_from_complementary_263_line_then_isomorphism",
        "degree": 263,
        "source_curve_id": target["curve_id"],
        "target_curve_id": source["curve_id"],
        "kernel_polynomial_coefficients": dual[
            "dual_kernel_polynomial_coefficients"],
        "raw_codomain_coefficients": dual["dual_raw_codomain_ainvs"],
        "isomorphism_tuple_to_source": dual["isomorphism_tuple_to_source"],
        "composition_sign": dual[
            "composition_sign_for_chosen_isomorphism"],
        "construction": "Sage 10.9 EllipticCurve.isogeny(kernel,check=True); sign*isomorphism_to(source)",
    }
    kernel_certificate = {
        "degree": 263,
        "forward_kernel_polynomial_sha256": forward[
            "kernel_polynomial_sha256"],
        "cyclic_subgroup_verified_by_sage_109": True,
        "dual_cyclic_subgroup_verified_by_sage_109": True,
        "kernel_x_coordinates_in_base_field": True,
        "frobenius_131_on_forward_kernel": "negation",
    }
    transport_certificate = {
        "subgroup_order": r,
        "source_generator": forward["source_generator"],
        "transported_generator": forward["transported_generator"],
        "source_public_fixture": forward["source_public_fixture"],
        "transported_public_fixture": forward[
            "transported_public_fixture"],
        "fixture_scalar": forward["fixture_scalar"],
        "source_and_target_order_r": True,
        "scalar_replay": True,
        "dual_after_forward_equals_263_on_generator_and_fixture": True,
    }
    edge_id = "e263d1_" + digest(map_spec)[:12]
    route_record = {
        "source_curve_id": source["curve_id"],
        "target_curve_id": target["curve_id"],
        "ordered_edges": [{"edge_id": edge_id,
                           "degree": 263, "direction": "descending",
                           "source_level": 0, "target_level": 1,
                           "map_sha256": digest(map_spec),
                           "dual_map_sha256": digest(dual_spec),
                           "kernel_certificate_sha256": digest(
                               kernel_certificate),
                           "subgroup_transport_certificate_sha256": digest(
                               transport_certificate)}],
    }
    route_id = "IW1E263d1h" + digest(route_record)[:12]
    manifest = {
        "schema_version": 1,
        "candidate_id": None,
        "field": field,
        "curve_nodes": {"source": source, "target": target},
        "endomorphism": {
            "source_order_conductor": 1,
            "target_order_conductor": 263,
            "frobenius_order_conductor_over_f2_131": 38531015900842053623,
            "ell": 263,
            "source_volcano_level": 0,
            "target_volcano_level": 1,
            "direction_proof": "The source order Z[pi] has fundamental discriminant -7. At split ell=263 its two horizontal kernels are F2-stable; the constructed kernel is not and the codomain j differs from 1. The remaining ell-1 kernels descend to order conductor 263 by the ordinary volcano theorem.",
        },
        "isogeny": {"degree": 263, "direction": "descending",
                     "forward_map": map_spec, "dual_map": dual_spec,
                     "kernel_certificate": kernel_certificate,
                     "subgroup_transport_certificate": transport_certificate},
        "route_id": route_id,
        "edge_id": edge_id,
        "route_identity_record": route_record,
        "evidence": {
            "forward_report_sha256": forward_sha,
            "dual_report_sha256": dual_sha,
            "independent_replay_sha256": replay_sha,
            "exceptional_replay_sha256": exceptional_sha,
            "exceptional_runtime_info_sha256": runtime_sha,
        },
        "scope": "Verified isogeny route and subgroup transport only. No factor base, point decomposition, recovered DLP, or IC-versus-rho timing is asserted.",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    path = HERE / "ecc2k130_degree263_route_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"source_curve_id": source["curve_id"],
                      "target_curve_id": target["curve_id"],
                      "route_id": route_id,
                      "edge_id": edge_id,
                      "map_sha256": digest(map_spec),
                      "dual_map_sha256": digest(dual_spec),
                      "kernel_certificate_sha256": digest(kernel_certificate),
                      "subgroup_transport_certificate_sha256": digest(
                          transport_certificate)}, indent=2))


if __name__ == "__main__":
    main()
