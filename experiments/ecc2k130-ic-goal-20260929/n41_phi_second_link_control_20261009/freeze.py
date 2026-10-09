#!/usr/bin/env sage -python
"""Freeze a public N41 phi-chain target and an exact second-link lookup arm."""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
TEMPLATE = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m16_static")
sys.path.insert(0, str(TEMPLATE))
import phi_frobenius_sat_gate_m16_sparse_seed_v1 as template

N, DIM, M = 41, 6, 12
R = 549756390943
SEED = 202610091330
SOLVER = Path("/opt/homebrew/bin/cryptominisat5")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def point_at(onb, curve, basis, code, position):
    mask = 0
    for bit, base in enumerate(basis):
        if (code >> bit) & 1:
            mask ^= base
    phi = onb.frob(onb.fromCoords(mask), position)
    if phi == onb.zero():
        raise ValueError("zero phi")
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("valid selector lost a curve point")
    return phi, point


def phi_of(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("nonfinite chain point")
    return onb.inv(onb.add(point[0], onb.one()))


def make_formula(source, destination, variables, records, units, rows=None):
    new_variables = variables if rows is None else variables + len(rows) + 1
    added = len(units)
    if rows is not None:
        added += sum(DIM + 1 + N + bin(a ^ b).count("1")
                     for _, a, b in rows)
    with source.open("rt", encoding="ascii") as src, destination.open(
            "x", encoding="ascii") as dst:
        if src.readline().split() != ["p", "cnf", str(variables), str(records)]:
            raise ValueError("source formula header changed")
        dst.write(f"p cnf {new_variables} {records + added}\n")
        for line in src:
            dst.write(line)
        for literal in units:
            dst.write(f"{literal} 0\n")
        if rows is not None:
            sign = new_variables
            leaf2 = list(range(2 + 2 * DIM, 2 + 3 * DIM))
            partial1 = list(range(2 + M * DIM + N, 2 + M * DIM + 2 * N))
            if len(leaf2) != DIM or len(partial1) != N:
                raise ValueError("primary layout changed")
            for index, (code, mask0, mask1) in enumerate(rows):
                selector = variables + 1 + index
                mismatch = []
                for bit, variable in enumerate(leaf2):
                    truth = variable if (code >> bit) & 1 else -variable
                    dst.write(f"{-selector} {truth} 0\n")
                    mismatch.append(-truth)
                dst.write(" ".join(str(value) for value in [*mismatch, selector]) + " 0\n")
                for bit, output in enumerate(partial1):
                    bit0 = (mask0 >> bit) & 1
                    bit1 = (mask1 >> bit) & 1
                    lit0 = output if bit0 else -output
                    if bit0 == bit1:
                        dst.write(f"{-selector} {lit0} 0\n")
                    else:
                        lit1 = output if bit1 else -output
                        dst.write(f"{-selector} {sign} {lit0} 0\n")
                        dst.write(f"{-selector} {-sign} {lit1} 0\n")
    return new_variables, records + added


def main():
    paths = [HERE / name for name in ("source.xcnf", "source_pinned.xcnf",
                                       "lookup.xcnf", "table.json", "protocol.json")]
    if any(path.exists() for path in paths):
        raise FileExistsError("preserve prior N41 frozen control")
    runtime = HERE / "runtime_info.json"
    if json.loads(runtime.read_text())["status"] != "verified":
        raise ValueError("checked Sage runtime is unverified")
    template.N, template.DIM, template.M = N, DIM, M
    onb = template.field.Onb(N)
    curve = template.curves.Curve(onb)
    basis = [1 << bit for bit in range(DIM)]
    valid_codes = []
    for code in range(1, 1 << DIM):
        try:
            _, point = point_at(onb, curve, basis, code, 0)
        except ValueError:
            continue
        subgroup_point = curve.mul(point, 4)
        if subgroup_point is None or curve.mul(subgroup_point, R) is not None:
            continue
        valid_codes.append(code)
    if len(valid_codes) != 30:
        raise ValueError("exact N41 phi domain changed")

    rng = random.Random(SEED)
    generator = curve.randomPointOfOrder(R, 4, rng)
    scalar = rng.randrange(1, R)
    target = curve.mul(generator, scalar)
    endpoint = curve.mul(target, pow(4, -1, R))
    if (target is None or endpoint is None or
            curve.mul(endpoint, 4) != target or
            curve.mul(generator, R) is not None):
        raise ValueError("N41 public target fixture invalid")
    endpoint_phi = phi_of(onb, endpoint)
    endpoint_mask = onb.toCoords(endpoint_phi)

    selector_seed = hashlib.sha256(
        f"N41-phi-second-link-control-{SEED}".encode()).digest()
    code0 = valid_codes[int.from_bytes(selector_seed[:8], "big") % len(valid_codes)]
    code1 = valid_codes[int.from_bytes(selector_seed[8:16], "big") % len(valid_codes)]
    phi0, point0 = point_at(onb, curve, basis, code0, 0)
    phi1, point1 = point_at(onb, curve, basis, code1, 1)
    first_masks = sorted({
        onb.toCoords(phi_of(onb, curve.add(point0, point1))),
        onb.toCoords(phi_of(onb, curve.add(point0, curve.neg(point1)))),
    })
    if len(first_masks) != 2:
        raise ValueError("first link lost a quadratic root")
    root_mask = first_masks[0]
    root_phi = onb.fromCoords(root_mask)
    root_point = curve.pointFromX(onb.add(onb.inv(root_phi), onb.one()))
    if root_point is None:
        raise ValueError("first-link root does not lift")
    rows = []
    for code in valid_codes:
        leaf_phi, leaf_point = point_at(onb, curve, basis, code, 2)
        a = onb.mul(onb.add(onb.sqr(root_phi), root_phi),
                    onb.add(onb.sqr(leaf_phi), leaf_phi))
        if onb.add(a, onb.one()) == onb.zero():
            raise ValueError("second-link quadratic degree drop")
        masks = sorted({
            onb.toCoords(phi_of(onb, curve.add(root_point, leaf_point))),
            onb.toCoords(phi_of(onb, curve.add(root_point, curve.neg(leaf_point)))),
        })
        if len(masks) != 2:
            raise ValueError("second-link root count changed")
        for mask in masks:
            value = onb.fromCoords(mask)
            total = onb.add(onb.add(root_phi, leaf_phi), value)
            if onb.add(onb.mul(a, onb.add(onb.sqr(value), value)),
                       onb.sqr(total)) != onb.zero():
                raise ValueError("second-link group root fails S3")
        rows.append([code, masks[0], masks[1]])

    formula, primary, roots, _prog, _nodes, _linear = template.build_formula(
        onb, basis, valid_codes, [endpoint_mask] * 4)
    if (len(roots) != (M - 1) * N or
            primary["leaf0"] != list(range(2, 2 + DIM)) or
            primary["leaf2"] != list(range(2 + 2 * DIM, 2 + 3 * DIM)) or
            primary["partial1"] != list(range(2 + M * DIM + N,
                                              2 + M * DIM + 2 * N))):
        raise ValueError("N41 formula primary layout changed")
    source = paths[0]
    formula.writeDimacs(source)
    with source.open("rt", encoding="ascii") as stream:
        header = stream.readline().split()
    if header[:2] != ["p", "cnf"]:
        raise ValueError("invalid source XCNF")
    variables, records = int(header[2]), int(header[3])
    units = []
    for name, code in (("leaf0", code0), ("leaf1", code1)):
        units.extend(variable if (code >> bit) & 1 else -variable
                     for bit, variable in enumerate(primary[name]))
    units.extend(variable if (root_mask >> bit) & 1 else -variable
                 for bit, variable in enumerate(primary["partial0"]))
    pinned = paths[1]
    make_formula(source, pinned, variables, records, units)
    lookup = paths[2]
    make_formula(source, lookup, variables, records, units, rows)

    table = {
        "kind": "n41_phi_second_link_exact_table", "status": "FROZEN",
        "basis_coordinate_masks": basis, "valid_codes": valid_codes,
        "first_link_leaf_codes": [code0, code1],
        "first_link_root_masks": first_masks,
        "selected_first_link_root": root_mask,
        "rows": rows,
    }
    paths[3].write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")
    protocol = {
        "kind": "n41_phi_second_link_ordinary_public_target_control",
        "status": "FROZEN", "proposal_id": "Q20261009133000",
        "candidate_id": None, "run_id": None, "curve_id": None,
        "workload_id": None, "target_count": 1, "batch": False,
        "field_degree": N, "subgroup_order": R, "cofactor": 4,
        "summands": M, "domain_dimension": DIM,
        "valid_selector_count": len(valid_codes),
        "generator_coordinates": list(map(onb.toCoords, generator)),
        "target_coordinates": list(map(onb.toCoords, target)),
        "target_fixture_scalar": scalar,
        "endpoint_coordinates": list(map(onb.toCoords, endpoint)),
        "endpoint_phi_mask": endpoint_mask,
        "leaf_codes": [code0, code1], "first_root_mask": root_mask,
        "solver": str(SOLVER),
        "solver_flags": ["--threads=1", "--verb=1", "--printsol=1",
                         "--xor=0", "--random=2026100913"],
        "per_arm_wall_cap_seconds": 120,
        "combined_rss_cap_bytes": 2147483648,
        "run_order": ["baseline", "lookup"],
        "source_sha256": {"runtime": sha(runtime), "template": sha(TEMPLATE / "phi_frobenius_sat_gate_m16_sparse_seed_v1.py"),
                          "freeze": sha(Path(__file__)), "source": sha(source),
                          "source_pinned": sha(pinned), "lookup": sha(lookup),
                          "table": sha(paths[3]), "solver": sha(SOLVER)},
        "accounting_boundary": "one public target point; fixture construction and target-independent setup outside paired solver-stage intervals",
    }
    paths[4].write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "FROZEN", "valid_codes": len(valid_codes),
                      "source_variables": variables, "source_records": records,
                      "root": root_mask}))


if __name__ == "__main__":
    main()
