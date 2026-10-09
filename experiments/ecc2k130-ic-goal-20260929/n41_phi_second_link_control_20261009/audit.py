#!/usr/bin/env sage -python
"""Independently audit the N41 public-target lookup control and its models."""

import hashlib
import json
import sys
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
CODEGEN = GOAL.parents[1] / "ecc2k130/codegen"
VERIFIER = (GOAL / "n131_phi_torsion_frobenius_domains_20261005/"
            "m16_prefix_audit_20261006")
sys.path[:0] = [str(CODEGEN), str(VERIFIER)]
import curves
import field
import verify_xcnf_model as xcnf

N, DIM, M = 41, 6, 12


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def record(values):
    return " ".join(str(value) for value in values) + " 0\n"


def verify_source_assignment(formula, values):
    variables, declared = xcnf.header(formula)
    checked = 0
    with formula.open("rt", encoding="ascii") as stream:
        for line in stream:
            if line.startswith(("p ", "c")) or not line.strip():
                continue
            parts = line.split()
            if not parts or parts[-1] != "0":
                raise ValueError("malformed source XCNF record")
            is_xor = parts[0].startswith("x")
            if is_xor:
                parts[0] = parts[0][1:]
            literals = [int(item) for item in parts[:-1]]
            if not literals or any(abs(value) > variables for value in literals):
                raise ValueError("source XCNF literal out of range")
            truth = [values[abs(value)] if value > 0 else not values[abs(value)]
                     for value in literals]
            if (sum(truth) % 2 == 1 if is_xor else any(truth)) is not True:
                raise ValueError("model falsifies source XCNF record")
            checked += 1
    if checked != declared:
        raise ValueError("source XCNF record count changed")
    return {"status": "PASS", "variables": variables, "satisfied_records": checked}


def point_phi(onb, point):
    if point is None or point[0] == onb.one():
        raise ValueError("nonfinite point in group replay")
    return onb.toCoords(onb.inv(onb.add(point[0], onb.one())))


def leaf(onb, curve, basis, code, position):
    phi_mask = 0
    for bit, mask in enumerate(basis):
        if (code >> bit) & 1:
            phi_mask ^= mask
    phi = onb.frob(onb.fromCoords(phi_mask), position)
    if phi == onb.zero():
        raise ValueError("zero leaf phi")
    point = curve.pointFromX(onb.add(onb.inv(phi), onb.one()))
    if point is None:
        raise ValueError("leaf code did not lift")
    return phi, point


def check_group(protocol, table):
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    generator = tuple(onb.fromCoords(item) for item in protocol["generator_coordinates"])
    target = tuple(onb.fromCoords(item) for item in protocol["target_coordinates"])
    endpoint = tuple(onb.fromCoords(item) for item in protocol["endpoint_coordinates"])
    r = protocol["subgroup_order"]
    if (not curve.onCurve(generator) or not curve.onCurve(target) or
            not curve.onCurve(endpoint) or curve.mul(generator, r) is not None or
            curve.mul(target, r) is not None or
            curve.mul(generator, protocol["target_fixture_scalar"]) != target or
            curve.mul(endpoint, 4) != target or
            point_phi(onb, endpoint) != protocol["endpoint_phi_mask"]):
        raise ValueError("public target or scalar fixture fails group replay")
    basis = table["basis_coordinate_masks"]
    if basis != [1 << bit for bit in range(DIM)]:
        raise ValueError("N41 basis changed")
    codes = []
    for code in range(1, 1 << DIM):
        try:
            _, point = leaf(onb, curve, basis, code, 0)
        except ValueError:
            continue
        projected = curve.mul(point, 4)
        if projected is not None and curve.mul(projected, r) is None:
            codes.append(code)
    if codes != table["valid_codes"] or len(codes) != 30:
        raise ValueError("valid factor-base selectors differ")
    c0, c1 = table["first_link_leaf_codes"]
    _, p0 = leaf(onb, curve, basis, c0, 0)
    _, p1 = leaf(onb, curve, basis, c1, 1)
    roots = sorted({point_phi(onb, curve.add(p0, p1)),
                    point_phi(onb, curve.add(p0, curve.neg(p1)))})
    if (roots != table["first_link_root_masks"] or len(roots) != 2 or
            table["selected_first_link_root"] != protocol["first_root_mask"]):
        raise ValueError("first-link root declaration changed")
    root_phi = onb.fromCoords(protocol["first_root_mask"])
    root_point = curve.pointFromX(onb.add(onb.inv(root_phi), onb.one()))
    if root_point is None:
        raise ValueError("selected root does not lift")
    all_masks = []
    if len(table["rows"]) != len(codes):
        raise ValueError("second-link table incomplete")
    for code, (row_code, mask0, mask1) in zip(codes, table["rows"]):
        if row_code != code or not (0 < mask0 < mask1 < (1 << N)):
            raise ValueError("second-link row malformed")
        leaf_phi, third = leaf(onb, curve, basis, code, 2)
        a = onb.mul(onb.add(onb.sqr(root_phi), root_phi),
                    onb.add(onb.sqr(leaf_phi), leaf_phi))
        leading = onb.add(a, onb.one())
        if leading == onb.zero():
            raise ValueError("second-link quadratic degree dropped")
        constant = onb.sqr(onb.add(root_phi, leaf_phi))
        values = [onb.fromCoords(mask0), onb.fromCoords(mask1)]
        for value in values:
            equation = onb.add(onb.add(onb.mul(leading, onb.sqr(value)),
                                      onb.mul(a, value)), constant)
            if equation != onb.zero():
                raise ValueError("second-link mask fails S3")
        if onb.add(values[0], values[1]) != onb.mul(a, onb.inv(leading)):
            raise ValueError("second-link masks are not the complete roots")
        group_masks = sorted((point_phi(onb, curve.add(root_point, third)),
                              point_phi(onb, curve.add(root_point, curve.neg(third)))))
        if group_masks != [mask0, mask1]:
            raise ValueError("second-link masks fail group addition")
        all_masks.extend((mask0, mask1))
    return {"valid_codes": len(codes), "verified_table_rows": len(codes),
            "verified_group_outputs": len(all_masks),
            "distinct_group_outputs": len(set(all_masks))}


def check_formulas(protocol, table):
    source, pinned, lookup = (HERE / name for name in
                              ("source.xcnf", "source_pinned.xcnf", "lookup.xcnf"))
    for name, path in (("source", source), ("source_pinned", pinned),
                       ("lookup", lookup)):
        if protocol["source_sha256"][name] != sha(path):
            raise ValueError(f"{name} formula hash changed")
    with source.open("rt", encoding="ascii") as original, pinned.open(
            "rt", encoding="ascii") as base, lookup.open(
            "rt", encoding="ascii") as guided:
        h0, h1, h2 = (stream.readline().split() for stream in
                      (original, base, guided))
        if h0[:2] != ["p", "cnf"]:
            raise ValueError("source XCNF header invalid")
        variables, records = int(h0[2]), int(h0[3])
        expected_units = 2 * DIM + N
        codes = table["valid_codes"]
        added = sum(DIM + 1 + N + bin(mask0 ^ mask1).count("1")
                    for _, mask0, mask1 in table["rows"])
        sign = variables + len(codes) + 1
        if (h1 != ["p", "cnf", str(variables), str(records + expected_units)] or
                h2 != ["p", "cnf", str(sign), str(records + expected_units + added)]):
            raise ValueError("paired XCNF dimensions changed")
        for line in original:
            if base.readline() != line or guided.readline() != line:
                raise ValueError("base source XCNF records changed")
        units = []
        for position, code in enumerate(table["first_link_leaf_codes"]):
            for bit in range(DIM):
                variable = 2 + position * DIM + bit
                units.append(variable if (code >> bit) & 1 else -variable)
        for bit in range(N):
            variable = 2 + M * DIM + bit
            units.append(variable if (protocol["first_root_mask"] >> bit) & 1
                         else -variable)
        for literal in units:
            line = record([literal])
            if base.readline() != line or guided.readline() != line:
                raise ValueError("leaf or first-root unit pin changed")
        if base.readline():
            raise ValueError("baseline formula gained unexpected clauses")
        count = 0
        for index, (code, mask0, mask1) in enumerate(table["rows"]):
            selector = variables + index + 1
            mismatch = []
            for bit in range(DIM):
                variable = 2 + 2 * DIM + bit
                truth = variable if (code >> bit) & 1 else -variable
                if guided.readline() != record([-selector, truth]):
                    raise ValueError("selector implication changed")
                mismatch.append(-truth)
                count += 1
            if guided.readline() != record([*mismatch, selector]):
                raise ValueError("selector converse changed")
            count += 1
            for bit in range(N):
                variable = 2 + M * DIM + N + bit
                value0, value1 = (mask0 >> bit) & 1, (mask1 >> bit) & 1
                literal0 = variable if value0 else -variable
                if value0 == value1:
                    if guided.readline() != record([-selector, literal0]):
                        raise ValueError("fixed next-coordinate bit changed")
                    count += 1
                else:
                    literal1 = variable if value1 else -variable
                    if (guided.readline() != record([-selector, sign, literal0]) or
                            guided.readline() != record([-selector, -sign, literal1])):
                        raise ValueError("root-choice output bit changed")
                    count += 2
        if guided.readline() or count != added:
            raise ValueError("lookup XCNF suffix or clause count changed")
    return {"source_variables": variables, "source_records": records,
            "unit_pins": expected_units, "lookup_variables": sign,
            "lookup_records": records + expected_units + added,
            "appended_lookup_clauses": added}


def preflight():
    output = HERE / "preflight.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, table_path, runtime_path = (HERE / name for name in
                                              ("protocol.json", "table.json", "runtime_info.json"))
    protocol = json.loads(protocol_path.read_text())
    table = json.loads(table_path.read_text())
    if (protocol["status"] != "FROZEN" or table["status"] != "FROZEN" or
            protocol["target_count"] != 1 or protocol["batch"] is not False or
            protocol["source_sha256"]["table"] != sha(table_path) or
            protocol["source_sha256"]["runtime"] != sha(runtime_path) or
            json.loads(runtime_path.read_text())["status"] != "verified"):
        raise ValueError("frozen one-target inputs changed")
    group = check_group(protocol, table)
    formulas = check_formulas(protocol, table)
    receipt = {
        "kind": "n41_phi_second_link_public_target_preflight",
        "status": "PASS_EXACT_GROUP_AND_XCNF", "proposal_id": protocol["proposal_id"],
        "candidate_id": None, "run_id": None,
        "target_count": 1, "group": group, "formulas": formulas,
        "source_sha256": {"protocol": sha(protocol_path), "table": sha(table_path),
                          "runtime": sha(runtime_path),
                          "auditor": sha(Path(__file__))},
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"], "group": group}))


def terminal():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError(output)
    protocol_path, result_path, preflight_path = (HERE / name for name in
                                                  ("protocol.json", "result.json", "preflight.json"))
    protocol = json.loads(protocol_path.read_text())
    result = json.loads(result_path.read_text())
    ready = json.loads(preflight_path.read_text())
    if (ready["status"] != "PASS_EXACT_GROUP_AND_XCNF" or
            ready["source_sha256"]["protocol"] != sha(protocol_path) or
            result["source_sha256"]["protocol"] != sha(protocol_path) or
            result["status"] == "RUNNING" or len(result["attempts"]) != 2):
        raise ValueError("terminal receipts incomplete")
    onb = field.Onb(N)
    curve = curves.Curve(onb)
    table = json.loads((HERE / "table.json").read_text())
    target = tuple(onb.fromCoords(item) for item in protocol["target_coordinates"])
    checked = []
    for index, arm in enumerate(protocol["run_order"]):
        row = result["attempts"][index]
        if row["arm"] != arm:
            raise ValueError("paired run order changed")
        process_path = HERE / f"{arm}.process.json"
        process = json.loads(process_path.read_text())
        try:
            live = psutil.Process(process["pid"])
        except psutil.NoSuchProcess:
            live = None
        if (live is not None and abs(live.create_time() - process["create_time_epoch"]) < .05
                and live.is_running() and live.status() != psutil.STATUS_ZOMBIE):
            raise ValueError("solver process remains live")
        formula = HERE / ("source_pinned.xcnf" if arm == "baseline" else "lookup.xcnf")
        stdout = HERE / f"{arm}.stdout.txt"
        for key, path in (("formula", formula), ("stdout", stdout),
                          ("stderr", HERE / f"{arm}.stderr.txt"),
                          ("process", process_path)):
            if row["source_sha256"][key] != sha(path):
                raise ValueError(f"{arm} {key} hash mismatch")
        if row["wall_seconds"] > protocol["per_arm_wall_cap_seconds"] + 15:
            raise ValueError("solver interval exceeded cap")
        replay = None
        if row["status"] == "SAT_MODEL_PENDING_REPLAY":
            model_check = xcnf.verify(formula, stdout)
            values = xcnf.model_from_stdout(stdout, model_check["variables"])
            source_check = verify_source_assignment(HERE / "source.xcnf", values)
            codes = [sum(1 << bit for bit in range(DIM)
                         if values[2 + position * DIM + bit])
                     for position in range(M)]
            if any(code not in table["valid_codes"] for code in codes):
                raise ValueError("solver used a non-base leaf")
            running = None
            partials = []
            for position, code in enumerate(codes):
                _, point = leaf(onb, curve, table["basis_coordinate_masks"],
                                code, position)
                for signed in (point, curve.neg(point)):
                    candidate = curve.add(running, signed)
                    if position == 0:
                        break
                    wanted = sum(1 << bit for bit in range(N)
                                 if values[2 + M * DIM + (position - 1) * N + bit]) if position < M - 1 else None
                    if (candidate is not None and candidate[0] != onb.one() and
                            (point_phi(onb, candidate) == wanted if wanted is not None
                             else curve.mul(candidate, 4) in
                             (target, curve.neg(target)))):
                        break
                else:
                    raise ValueError("no signed leaf realizes model partial")
                running = candidate
                if 1 <= position < M - 1:
                    partials.append(point_phi(onb, running))
            if curve.mul(running, 4) not in (target, curve.neg(target)):
                raise ValueError("model sum does not project to the public target")
            replay = {"status": "PASS_GROUP_REPLAY", "leaf_codes": codes,
                      "partial_phi_masks": partials,
                      "projected_target_sign": 0 if curve.mul(running, 4) == target else 1,
                      "xcnf_model_check": model_check,
                      "source_model_check": source_check}
        checked.append({"arm": arm, "status": row["status"],
                        "wall_seconds": row["wall_seconds"],
                        "model_lines": row["model_lines"], "replay": replay})
    receipt = {"kind": "n41_phi_second_link_public_target_terminal_audit",
               "status": "PASS_TERMINAL_AND_REPLAY", "proposal_id": protocol["proposal_id"],
               "candidate_id": None, "run_id": None,
               "target_count": 1, "arms": checked,
               "source_sha256": {"protocol": sha(protocol_path),
                                 "result": sha(result_path),
                                 "preflight": sha(preflight_path),
                                 "auditor": sha(Path(__file__))}}
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": receipt["status"],
                      "replayed": [item["replay"] is not None for item in checked]}))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("preflight", "terminal"):
        raise SystemExit("usage: ./sage -python audit.py preflight|terminal")
    (preflight if sys.argv[1] == "preflight" else terminal)()
