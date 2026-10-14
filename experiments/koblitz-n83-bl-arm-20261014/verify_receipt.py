#!/usr/bin/env python3
"""Audit an n=83 BL-arm receipt and apply the frozen decision rule.

Reads the receipt directory the workflow uploads (layout in README.md,
"Receipt"), re-checks every gate the protocol names, replays every recovered
scalar in the pinned pure-Python oracle, computes the frozen statistics and
writes `result.json` and `result_table.md` next to the receipt. Python here
only audits and summarises recorded values; every measured number comes from a
producer's own record.

Exit status 0 means the audit ran, not that any reading is favourable; an
ineligible reading is reported as `no_result`.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "snapshot"
sys.path.insert(0, str(HERE))
import bl_tools as bt  # noqa: E402


def load(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def oracle_curve():
    sys.path.insert(0, str(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab"))
    import single_target_panel as panel  # noqa: E402
    beats = load(SNAPSHOT / "research/sat_factor_base_review_20260908/autolab/protocol.json")["beats"]
    return panel.cached_curve(dict(beats["koblitz.compact_orbit.n83_single_target"]["curve_fixture"]))


def bootstrap(pairs, statistic, seed, draws):
    rng = random.Random(seed)
    n = len(pairs)
    values = sorted(statistic([pairs[rng.randrange(n)] for _ in range(n)]) for _ in range(draws))
    return [values[int(0.025 * draws)], values[int(0.975 * draws) - 1]]


def ratio_of_means(index_num, index_den):
    def statistic(sample):
        return (sum(p[index_num] for p in sample) / len(sample)) / (sum(p[index_den] for p in sample) / len(sample))
    return statistic


def reading(interval, eligible, faster_if_above, faster_if_below):
    if not eligible or interval is None:
        return "no_result"
    if interval[0] > 1:
        return faster_if_above
    if interval[1] < 1:
        return faster_if_below
    return "not_separated"


def median(values):
    values = sorted(values)
    n = len(values)
    if not n:
        return None
    return values[n // 2] if n % 2 else 0.5 * (values[n // 2 - 1] + values[n // 2])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    root = args.receipt.resolve()
    protocol = load(HERE / "protocol.json")
    stats = protocol["statistics"]
    issues = []

    def gate(name, ok, detail=""):
        if not ok:
            issues.append(name + (": " + detail if detail else ""))
        return ok

    impl_value = protocol["rho_reference"]["value"]
    start = load(root / "panel/runner_start.json")
    impl = start["implementation"]
    smoke = bool(start.get("implementation_overridden_for_smoke")) or start.get("targets_limit") is not None
    gate("implementation is the protocol's rho reference", smoke or impl == impl_value,
         "receipt %s, protocol %s" % (impl, impl_value))
    gate("protocol unchanged since the run", start["protocol_sha256"] == bt.sha256(HERE / "protocol.json"))
    spec = protocol["rho_step_implementations"][impl]

    # Positive control (counts), for the chosen implementation.
    control = load(root / "control/summary.json") if (root / "control/summary.json").exists() else None
    wanted = [c["id"] for c in protocol["controls"]["positive"]["runs"] if c["implementation"] == impl]
    control_rows = {c["id"]: c for c in (control or {}).get("controls", [])}
    positive_ok = bool(control) and all(control_rows.get(i, {}).get("status") == "PASS" for i in wanted)
    gate("positive control passed for the chosen implementation", positive_ok, ",".join(wanted))

    # IC precompute: full rank, table identical to B's, P_IC recorded.
    ic_pre = load(root / "ic_precompute/precompute_receipt.json")
    gate("IC precompute passed", ic_pre.get("status") == "PASS")
    p_ic = ic_pre.get("P_IC_ms")

    # BL table: budget matched, stored exactly, checked three ways.
    bl_pre = load(root / "bl/precompute_receipt.json")
    table_checks = load(root / "bl/table_checks.json")
    gate("BL precompute passed (budget reached, not overrun)", bl_pre.get("status") == "PASS")
    gate("BL table checks passed (regeneration, every record, oracle sample)", table_checks.get("status") == "PASS")
    gate("BL budget is this job's P_IC", smoke or abs(bl_pre["budget_ms"] - (p_ic or -1)) < 1e-6)
    gate("BL table built for the chosen implementation", bl_pre["implementation"] == impl)
    producer = bl_pre["producer"]

    # Panel rows.
    rows = jsonl(root / "panel/runs.jsonl")
    ran = [r for r in rows if r["status"] in ("valid", "invalid")]
    invalid = [r for r in ran if r["status"] != "valid"]
    skipped = [r for r in rows if r["status"].startswith("skipped")]
    gate("every run valid", not invalid, "; ".join("%d %s" % (r["serial"], r["issues"]) for r in invalid[:10]))
    if not smoke:
        gate("no run skipped", not skipped, "%d skipped" % len(skipped))
    curve = oracle_curve()
    targets = load(HERE / protocol["inputs"]["targets_file"])
    points = {"q0": [int(v) for v in targets["q0"]["point"]]}
    points.update({"w%02d" % e["seed"]: [int(v) for v in e["point"]] for e in targets["panel_b"]["points"]})
    sidecar = int(load(SNAPSHOT / protocol["inputs"]["validation_fixture"])["fixture_scalar_validation_only"])
    scalars = {}
    replays = {}
    for r in ran:
        if r["status"] != "valid":
            continue
        d = int(r["fields"]["recovered_scalar"])
        scalars.setdefault(r["point_id"], set()).add(d)
    for point_id, found in sorted(scalars.items()):
        gate("one scalar per point (%s)" % point_id, len(found) == 1, str(sorted(found)))
        d = min(found)
        replays[point_id] = curve.mul(curve.g, d) == tuple(points[point_id])
        gate("oracle replay [d]G = Q (%s)" % point_id, replays[point_id])
    if "q0" in scalars:
        gate("Q0 scalar equals the validation sidecar", scalars["q0"] == {sidecar})

    def arm_rows(arm, panel=None):
        return [r for r in ran if r["arm"] == arm and r["status"] == "valid" and (panel is None or r["panel"] == panel)]

    # Work identities.
    for r in arm_rows("ic"):
        if r["point_id"] == "q0":
            gate("IC probes on Q0 equal B's 8,845,441", int(r["fields"]["ops"]) == protocol["controls"]["ic_work_identity"]["q0_probes"])
    bl_by = {(r["point_id"], r["seed"]): r for r in arm_rows("bl")}
    aa_by = {(r["point_id"], r["seed"]): r for r in arm_rows("bl_aa")}
    for key, r in bl_by.items():
        if key in aa_by:
            gate("BL A/A identical steps %s" % (key,), r["fields"]["ops"] == aa_by[key]["fields"]["ops"])
    plain = arm_rows("bl_plain")
    rho_q0 = [r for r in arm_rows("rho", "Q") if r["seed"] == protocol["controls"]["step_identity"]["seed"]]
    if plain and rho_q0:
        gate("step identity: BL binary without a table walks the reference's steps",
             plain[0]["fields"]["ops"] == rho_q0[0]["fields"]["ops"],
             "%s vs %s" % (plain[0]["fields"]["ops"], rho_q0[0]["fields"]["ops"]))
    elif not smoke:
        gate("step identity control ran", False)
    bl_solved = [r["fields"].get("solved_by") for r in arm_rows("bl") + arm_rows("bl_aa")]
    eligible = not issues

    # Statistics.
    def fval(r, key="online_ms"):
        return float(r["fields"][key])

    f_ids = sorted({r["point_id"] for r in arm_rows("bl", "F")})
    by = {arm: {r["point_id"]: r for r in arm_rows(arm, "F")} for arm in ("ic", "bl", "bl_aa", "rho")}
    triples = [(fval(by["ic"][p]), fval(by["bl"][p]), fval(by["rho"][p])) for p in f_ids
               if p in by["ic"] and p in by["rho"] and p in by["bl"]]
    result = {"kind": "n83_bl_arm_result", "implementation": impl, "smoke": smoke,
              "protocol_sha256": bt.sha256(HERE / "protocol.json"), "eligible": eligible, "issues": issues,
              "rows": {"ran": len(ran), "invalid": len(invalid), "skipped": len(skipped)}}
    if triples:
        draws, seed = stats["bootstrap_draws"], stats["bootstrap_seed"]
        mean = [sum(t[i] for t in triples) / len(triples) for i in range(3)]
        ic_over_bl = mean[0] / mean[1]
        rho_over_bl = mean[2] / mean[1]
        rho_over_ic = mean[2] / mean[0]
        ci_ic_bl = bootstrap(triples, ratio_of_means(0, 1), seed, draws) if len(triples) > 1 else None
        ci_rho_bl = bootstrap(triples, ratio_of_means(2, 1), seed + 1, draws) if len(triples) > 1 else None
        ci_rho_ic = bootstrap(triples, ratio_of_means(2, 0), seed + 2, draws) if len(triples) > 1 else None
        result["F"] = {
            "targets": len(triples),
            "mean_online_ms": {"ic": mean[0], "bl": mean[1], "rho": mean[2]},
            "median_online_ms": {"ic": median([t[0] for t in triples]), "bl": median([t[1] for t in triples]),
                                 "rho": median([t[2] for t in triples])},
            "ic_over_bl": {"value": ic_over_bl, "ci95": ci_ic_bl,
                           "reading": reading(ci_ic_bl, eligible, "bl_online_faster_than_ic", "ic_online_faster_than_bl"),
                           "rows_bl_faster": sum(t[1] < t[0] for t in triples)},
            "rho_over_bl": {"value": rho_over_bl, "ci95": ci_rho_bl,
                            "reading": reading(ci_rho_bl, eligible, "bl_online_faster_than_rho", "rho_online_faster_than_bl")},
            "rho_over_ic": {"value": rho_over_ic, "ci95": ci_rho_ic,
                            "reading": reading(ci_rho_ic, eligible, "ic_online_faster_than_rho", "rho_online_faster_than_ic")},
        }
    q_blocks = []
    for block in range(protocol["panels"]["Q"]["blocks"]):
        cell = {arm: [r for r in arm_rows(arm, "Q") if r["block"] == block] for arm in ("ic", "bl", "rho")}
        if all(cell.values()):
            ic_ms, bl_ms, rho_ms = (fval(cell[a][0]) for a in ("ic", "bl", "rho"))
            q_blocks.append({"block": block, "seed": cell["bl"][0]["seed"], "ic_ms": ic_ms, "bl_ms": bl_ms,
                             "rho_ms": rho_ms, "bl_steps": int(cell["bl"][0]["fields"]["ops"]),
                             "rho_steps": int(cell["rho"][0]["fields"]["ops"]),
                             "ic_over_bl": ic_ms / bl_ms, "rho_over_bl": rho_ms / bl_ms, "rho_over_ic": rho_ms / ic_ms})
    if q_blocks:
        result["Q"] = {"blocks": q_blocks,
                       "median_ic_over_bl": median([b["ic_over_bl"] for b in q_blocks]),
                       "median_rho_over_bl": median([b["rho_over_bl"] for b in q_blocks]),
                       "median_rho_over_ic": median([b["rho_over_ic"] for b in q_blocks]),
                       "note": "IC on Q0 is one deterministic scan (identical probes every block); BL and rho vary with the walk seed"}
    # Cold costs (one fresh target, empty caches): setup + online.
    all_bl = arm_rows("bl")
    all_ic = arm_rows("ic")
    all_rho = arm_rows("rho")
    if all_bl and all_ic and all_rho and p_ic:
        bl_setup = median([fval(r, "setup_ms") for r in all_bl])
        rho_setup = median([fval(r, "setup_ms") for r in all_rho])
        ic_setup_per_process = median([fval(r, "setup_ms") for r in all_ic])
        source = result.get("F", {}).get("mean_online_ms") or {
            "ic": sum(map(fval, all_ic)) / len(all_ic), "bl": sum(map(fval, all_bl)) / len(all_bl),
            "rho": sum(map(fval, all_rho)) / len(all_rho)}
        ic_cold = p_ic + source["ic"]
        bl_cold = producer["precompute_ms"] + bl_setup + source["bl"]
        rho_cold = rho_setup + source["rho"]
        result["cold"] = {
            "definition": protocol["statistics"]["cold"],
            "ic_ms": ic_cold, "bl_ms": bl_cold, "rho_ms": rho_cold,
            "ic_over_bl": ic_cold / bl_cold, "bl_over_rho": bl_cold / rho_cold, "ic_over_rho": ic_cold / rho_cold,
            "P_IC_ms": p_ic, "bl_precompute_ms": producer["precompute_ms"], "bl_setup_ms_median": bl_setup,
            "ic_setup_ms_per_process_median": ic_setup_per_process, "rho_setup_ms_median": rho_setup,
            "single_target_rho_online_ms_mean": source["rho"],
            "single_target_rho_online_ms_median": median(list(map(fval, arm_rows("rho", "F")))) if arm_rows("rho", "F") else None,
        }
    # A/A.
    aa = [(fval(bl_by[k]), fval(aa_by[k])) for k in bl_by if k in aa_by]
    if aa:
        logs = [math.log(b / a) for b, a in aa]
        rng = random.Random(stats["bootstrap_seed"] + 3)
        draws = stats["bootstrap_draws"]
        boot = sorted(sum(logs[rng.randrange(len(logs))] for _ in logs) / len(logs) for _ in range(draws))
        gm = math.exp(sum(logs) / len(logs))
        ci = [math.exp(boot[int(0.025 * draws)]), math.exp(boot[int(0.975 * draws) - 1])]
        band = protocol["controls"]["aa"]["band"]
        result["aa"] = {"pairs": len(aa), "geometric_mean_bl_over_bl_aa": gm, "ci95": ci, "band": band,
                        "status": "PASS" if band[0] <= ci[0] and ci[1] <= band[1] else "FAIL"}
    # The table and the model (secondary).
    r_order = int(producer["identity"]["subgroup_order"])
    automorphisms = int(producer["identity"]["automorphism_size"])
    ell = bt.classes(r_order, automorphisms)
    lanes = spec["bl"]["lanes"]
    dp = protocol["bl"]["dp_bits"]
    predicted = bt.predict_online_steps(r_order, automorphisms, lanes, dp, producer["covered_points"])
    bl_steps = [int(r["fields"]["ops"]) for r in arm_rows("bl")]
    result["table"] = {
        "entries_T": producer["table_entries"], "precompute_steps": producer["steps"],
        "precompute_ms": producer["precompute_ms"], "ns_per_step": producer["ns_per_step"],
        "covered_points": producer["covered_points"], "duplicate_points": producer["duplicate_points"],
        "fruitless": producer["fruitless"], "capped": producer["capped"], "dp_bits": dp, "lanes": lanes,
        "alpha": 2 ** dp * math.sqrt(producer["table_entries"] / ell),
        "sha256": bl_pre["table_sha256"], "blake3": producer["table_blake3"], "bytes": bl_pre["table_bytes"],
        "peak_rss_bytes_precompute": producer.get("peak_rss_bytes"),
        "budget_ms": bl_pre["budget_ms"], "precompute_over_budget": bl_pre.get("precompute_over_budget"),
        "matched_fraction": producer["precompute_ms"] / p_ic if p_ic else None,
        "model_online_steps": predicted,
        "measured_online_steps_mean": sum(bl_steps) / len(bl_steps) if bl_steps else None,
        "measured_over_model": (sum(bl_steps) / len(bl_steps)) / predicted if bl_steps else None,
        "solved_by_counts": {k: bl_solved.count(k) for k in sorted(set(map(str, bl_solved)))},
        "classes_l": ell,
    }
    result["positive_control"] = {i: control_rows.get(i) for i in wanted}
    result["step_identity"] = {"plain_steps": plain[0]["fields"]["ops"] if plain else None,
                               "reference_steps": rho_q0[0]["fields"]["ops"] if rho_q0 else None,
                               "plain_online_ms": fval(plain[0]) if plain else None,
                               "reference_online_ms": fval(rho_q0[0]) if rho_q0 else None}
    result["status"] = "COMPLETE" if eligible else "INELIGIBLE"
    (root / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["| quantity | value |", "| --- | --- |",
             "| implementation | %s |" % impl, "| status | %s |" % result["status"]]
    if "F" in result:
        F = result["F"]
        for key in ("ic_over_bl", "rho_over_bl", "rho_over_ic"):
            ci = F[key]["ci95"]
            lines.append("| F mean %s | %.3f [%s] %s |" % (key, F[key]["value"],
                         ", ".join("%.3f" % v for v in ci) if ci else "n/a", F[key]["reading"]))
        lines.append("| F mean online ms ic / bl / rho | %.2f / %.2f / %.2f |" % tuple(F["mean_online_ms"][a] for a in ("ic", "bl", "rho")))
    if "Q" in result:
        lines.append("| Q0 median ic/bl, rho/bl, rho/ic | %.3f, %.3f, %.3f |" % (
            result["Q"]["median_ic_over_bl"], result["Q"]["median_rho_over_bl"], result["Q"]["median_rho_over_ic"]))
    if "cold" in result:
        c = result["cold"]
        lines.append("| cold ms ic / bl / rho | %.0f / %.0f / %.0f |" % (c["ic_ms"], c["bl_ms"], c["rho_ms"]))
    t = result["table"]
    lines.append("| table T, steps, ns/step | %d, %d, %.1f |" % (t["entries_T"], t["precompute_steps"], t["ns_per_step"]))
    lines.append("| BL online steps measured / model | %s |" % ("%.3f" % t["measured_over_model"] if t["measured_over_model"] else "n/a"))
    if "aa" in result:
        lines.append("| A/A BL/BL' geometric mean [95%%] | %.3f [%.3f, %.3f] %s |" % (
            result["aa"]["geometric_mean_bl_over_bl_aa"], *result["aa"]["ci95"], result["aa"]["status"]))
    lines.append("| issues | %s |" % ("; ".join(issues) if issues else "none"))
    (root / "result_table.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": result["status"], "issues": issues, "F": result.get("F", {}).get("ic_over_bl")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
