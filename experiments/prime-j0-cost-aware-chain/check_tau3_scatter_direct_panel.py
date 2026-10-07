#!/usr/bin/env python3
"""Verify direct residual pairing on the fresh scattered-tau scalar fixture."""

import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def direct_pairs(blocks, selected, unit_maps):
    """Pair complete-table neighbors, then first available residual partners."""
    mate = [-1] * len(blocks)
    for x in range(len(blocks) - 1):
        if (mate[x] < 0 and mate[x + 1] < 0 and
                blocks[x][0] // 2 == blocks[x + 1][0] // 2):
            mate[x], mate[x + 1] = x + 1, x
    baseline_pairs = sum(mate[x] > x for x in range(len(blocks)))
    for x, (i, u) in enumerate(blocks):
        if mate[x] >= 0:
            continue
        for y in range(x + 1, len(blocks)):
            if mate[y] >= 0:
                continue
            j, v = blocks[y]
            rep = min((mapping[u], mapping[v]) for mapping in unit_maps)
            if (i, j, *rep) in selected:
                mate[x], mate[y] = y, x
                break
    return [(x, mate[x]) for x in range(len(blocks)) if mate[x] > x], baseline_pairs


def panel(repo, policy_path, design_path, inputs_path, exact_path, output):
    sys.path[:0] = [str(repo), str(HERE)]
    from make_tau3_fused import build, recode, block_pattern, tau, unit
    from make_tau3_scatter_design import unit_maps
    from check_tau3_scatter_panel import add, pattern_coeff, tau_power, apply_unit_point
    from run import representatives, point_add, point_mul

    policy_blob, design_blob = policy_path.read_bytes(), design_path.read_bytes()
    inputs_blob, exact_blob = inputs_path.read_bytes(), exact_path.read_bytes()
    policy, design = json.loads(policy_blob), json.loads(design_blob)
    inputs, exact = json.loads(inputs_blob), json.loads(exact_blob)
    assert policy["status"] == "frozen_retrospective_policy"
    assert policy["table_design_sha256"] == sha256(design_blob)
    assert inputs["policy_sha256"] == sha256(policy_blob)
    assert inputs["design_sha256"] == sha256(design_blob)
    assert exact["status"] == "verified_prospective_operation_panel"
    assert exact["inputs_sha256"] == sha256(inputs_blob)
    assert exact["design_sha256"] == sha256(design_blob)
    exact_rows = {row["case_id"]: row for row in exact["rows"]}
    designs = {record["curve"]: record for record in design["records"]}
    digits, residue, *_ = build()
    maps = unit_maps(digits, unit)
    previous = json.loads((repo / "compact-pos-panel.json").read_text())
    rows = []

    for case in inputs["cases"]:
        name = case["curve"]["name"]
        config = designs[name]
        selected = {(i, j, u, v) for i, j, u, v in config["entries"]}
        order, modulus, b = (case["curve"][key] for key in ("order", "p", "b"))
        point = int(case["base_x"]), int(case["base_y"])
        old_fields = next(row["fields"] for row in previous["rows"]
                          if row["case_id"] == case["id"] and row["mode"] == "pos-compact")
        endo_lambda = int(old_fields["endo_lambda"])
        omega_eigen = (order - endo_lambda) % order
        beta0 = next(pow(g, (modulus - 1) // 3, modulus) for g in range(2, 100)
                     if pow(g, (modulus - 1) // 3, modulus) != 1)
        omega_point = point_mul(point, omega_eigen, modulus, b)
        beta = next(value for value in (beta0, beta0 * beta0 % modulus)
                    if (value * point[0] % modulus, point[1]) == omega_point)
        scalar_blob = (inputs_path.parent / case["scalar_file"]).read_bytes()
        assert sha256(scalar_blob) == case["scalar_file_sha256"]

        base_adds = direct_adds = pair_count = extra_pairs = 0
        coefficient_checks = point_checks = 0
        for index, (scalar,) in enumerate(struct.iter_unpack("<Q", scalar_blob)):
            _, a, c = min(representatives(order, omega_eigen, scalar), key=lambda item: item[0])
            seq = recode(a, c, digits, residue)
            patterns = [block_pattern((seq[i:i + 3] + [0] * 3)[:3])
                        for i in range(0, len(seq), 3)]
            blocks = [(i, value) for i, value in enumerate(patterns) if value]
            baseline = sum(bool(patterns[i] or
                                (patterns[i + 1] if i + 1 < len(patterns) else 0))
                           for i in range(0, len(patterns), 2))
            pairs, baseline_pairs = direct_pairs(blocks, selected, maps)
            paired = {vertex for pair in pairs for vertex in pair}
            cost = len(blocks) - len(pairs)
            assert cost <= baseline
            base_adds += baseline
            direct_adds += cost
            pair_count += len(pairs)
            extra_pairs += len(pairs) - baseline_pairs

            coeff_sum = (0, 0)
            group_sum = None
            group_check = index < 16 or index % 512 == 0
            for x, y in pairs:
                (i, u), (j, v) = blocks[x], blocks[y]
                rep = min((mapping[u], mapping[v]) for mapping in maps)
                code = next(code for code, mapping in enumerate(maps)
                            if (mapping[rep[0]], mapping[rep[1]]) == (u, v))
                rep_coeff = add(tau_power(pattern_coeff(rep[0], digits, tau), 3 * i, tau),
                                tau_power(pattern_coeff(rep[1], digits, tau), 3 * j, tau))
                actual = unit(*rep_coeff, code)
                direct = add(tau_power(pattern_coeff(u, digits, tau), 3 * i, tau),
                             tau_power(pattern_coeff(v, digits, tau), 3 * j, tau))
                assert actual == direct
                coeff_sum = add(coeff_sum, actual)
                if group_check:
                    krep = (rep_coeff[0] + rep_coeff[1] * (1 + endo_lambda)) % order
                    prepared = point_mul(point, krep, modulus, b)
                    group_sum = point_add(
                        group_sum, apply_unit_point(prepared, code, beta, modulus), modulus, b)
            for x, (i, u) in enumerate(blocks):
                if x in paired:
                    continue
                rep = min(mapping[u] for mapping in maps)
                code = next(code for code, mapping in enumerate(maps) if mapping[rep] == u)
                rep_coeff = tau_power(pattern_coeff(rep, digits, tau), 3 * i, tau)
                actual = unit(*rep_coeff, code)
                direct = tau_power(pattern_coeff(u, digits, tau), 3 * i, tau)
                assert actual == direct
                coeff_sum = add(coeff_sum, actual)
                if group_check:
                    krep = (rep_coeff[0] + rep_coeff[1] * (1 + endo_lambda)) % order
                    prepared = point_mul(point, krep, modulus, b)
                    group_sum = point_add(
                        group_sum, apply_unit_point(prepared, code, beta, modulus), modulus, b)
            assert coeff_sum == (a, c)
            assert (coeff_sum[0] + coeff_sum[1] * (1 + endo_lambda)) % order == scalar % order
            coefficient_checks += 1
            if group_check:
                assert group_sum == point_mul(point, scalar, modulus, b)
                point_checks += 1

        exact_row = exact_rows[case["id"]]
        assert exact_row["verified"] and exact_row["base_adds"] == base_adds
        assert direct_adds >= exact_row["scatter_adds"]
        rows.append({"case_id": case["id"], "curve": name,
                     "scalars": coefficient_checks, "point_checks": point_checks,
                     "base_adds": base_adds, "exact_adds": exact_row["scatter_adds"],
                     "direct_adds": direct_adds,
                     "exact_savings": base_adds - exact_row["scatter_adds"],
                     "direct_savings": base_adds - direct_adds,
                     "lost_savings": direct_adds - exact_row["scatter_adds"],
                     "direct_matched_pairs": pair_count,
                     "direct_extra_pairs": extra_pairs, "verified": True})
        print(json.dumps(rows[-1], sort_keys=True), flush=True)

    report = {"schema": 1, "status": "verified_prospective_operation_panel",
              "cpu_timing_claim": None, "policy_sha256": sha256(policy_blob),
              "design_sha256": sha256(design_blob),
              "inputs_sha256": sha256(inputs_blob), "exact_panel_sha256": sha256(exact_blob),
              "source_sha256": sha256(Path(__file__).read_bytes()), "rows": rows}
    content = json.dumps(report, indent=2, sort_keys=True).encode() + b"\n"
    if output.exists() and output.read_bytes() != content:
        raise ValueError("frozen direct panel changed")
    output.write_bytes(content)
    return {"output_sha256": sha256(content), "rows": len(rows),
            "coefficient_checks": sum(row["scalars"] for row in rows),
            "point_checks": sum(row["point_checks"] for row in rows)}


if __name__ == "__main__":
    if len(sys.argv) != 7:
        raise SystemExit("usage: check_tau3_scatter_direct_panel.py REPO POLICY DESIGN INPUTS EXACT OUTPUT")
    print(json.dumps(panel(*map(Path, sys.argv[1:])), sort_keys=True))
