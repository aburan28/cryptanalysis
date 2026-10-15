#!/usr/bin/env python3
"""Audit a receipt of ic-probe-latency-20261015 and apply the frozen rule.

    analyse.py RECEIPT_DIR   # writes RECEIPT_DIR/result.json and result_table.md
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T975_3DF = 3.182


def tint(logs):
    k = len(logs)
    m = st.fmean(logs)
    if k < 2:
        return math.exp(m), [None, None]
    t = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571}.get(k - 1, 1.96)
    h = t * st.stdev(logs) / math.sqrt(k)
    return math.exp(m), [math.exp(m - h), math.exp(m + h)]


def main():
    receipt = Path(sys.argv[1])
    protocol = json.loads((HERE / "protocol.json").read_text())
    rows = [json.loads(l) for l in (receipt / "runs.jsonl").read_text().splitlines() if l.strip()]
    issues = []
    smoke = any(json.loads(p.read_text()).get("smoke") for p in receipt.glob("runner_start_*.json"))
    if smoke:
        protocol["ic_panel"]["pairs"] = protocol["smoke"]["ic_pairs"]
        protocol["rho_panel"]["pairs"] = protocol["smoke"]["rho_pairs"]
    exp_probes = protocol["ic_panel"]["expected_probes"]
    exp_steps = protocol["rho_panel"]["expected_steps"]
    scalar = protocol["inputs"]["q0_scalar_public"]

    # pointer-chase sweep
    sweep = {}
    for r in rows:
        if r["kind"] == "pchase" and r["phase"] in ("P1", "P2") and r["status"] == "valid":
            p = r["parsed"]
            sweep.setdefault((r["size"], r["mode"]), []).append(p)
    sweep_out = []
    for (size, mode), ps in sorted(sweep.items()):
        frac = [p["anon_huge_kb"] * 1024 / size for p in ps]
        sweep_out.append({"size_bytes": size, "mode": mode, "runs": len(ps),
                          "ns_per_access": st.median(p["ns_per_access_median"] for p in ps),
                          "ns_per_access_runs": [p["ns_per_access_median"] for p in ps],
                          "anon_huge_fraction": frac, "init_ms": [p["init_ms"] for p in ps]})
        if size >= 1 << 30 and mode == "thp" and min(frac) < 0.9:
            issues.append("pchase thp at %d bytes: anon huge fraction %.3f < 0.9" % (size, min(frac)))
        if mode == "4k" and max(frac) > 0:
            issues.append("pchase 4k at %d bytes shows huge pages" % size)
    for s in sorted({x["size_bytes"] for x in sweep_out}):
        a = {x["mode"]: x["ns_per_access"] for x in sweep_out if x["size_bytes"] == s}
        for x in sweep_out:
            if x["size_bytes"] == s and "4k" in a:
                x["over_4k"] = x["ns_per_access"] / a["4k"]

    def arm_rows(kind):
        out = {}
        for r in rows:
            if r["kind"] == kind and r["phase"] in ("P3", "P4"):
                out.setdefault(r["pair"], {})[r["mode"]] = r
        return out

    def check_arm(r, kind):
        f = r.get("parsed", {}).get("fields", {})
        pg = r.get("parsed", {}).get("pages", {})
        if r["status"] != "valid":
            issues.append("%s serial %d invalid: %s" % (kind, r["serial"], r["issues"]))
        ops = int(f.get("ops", "0") or 0)
        if kind == "ic":
            if ops != exp_probes:
                issues.append("ic serial %d: %d probes != %d" % (r["serial"], ops, exp_probes))
            if f.get("recovered_scalar") != scalar:
                issues.append("ic serial %d: scalar %s" % (r["serial"], f.get("recovered_scalar")))
            huge = pg.get("max_anon_huge_kb", 0)
            if r["mode"] == "thp" and huge < 2097152:
                issues.append("ic thp serial %d: max AnonHugePages %d kB < 2 GiB" % (r["serial"], huge))
            if r["mode"] == "4k" and huge != 0:
                issues.append("ic 4k serial %d: AnonHugePages %d kB" % (r["serial"], huge))
        else:
            if ops != exp_steps:
                issues.append("rho serial %d: %d steps != %d" % (r["serial"], ops, exp_steps))
            if f.get("recovered_scalar") != scalar:
                issues.append("rho serial %d: scalar %s" % (r["serial"], f.get("recovered_scalar")))
        return float(f.get("online_ms", "nan")) * 1e6 / ops if ops else float("nan")

    nulls = {}
    for r in rows:
        if r["kind"] == "pchase" and r["phase"] == "P3" and r["status"] == "valid":
            nulls[(r["pair"], r["mode"])] = r["parsed"]["ns_per_access_median"]

    def panel(kind):
        pairs = arm_rows(kind)
        out, logs = [], []
        for k in sorted(pairs):
            pr = pairs[k]
            if set(pr) != {"4k", "default", "thp"}:
                issues.append("%s block %d incomplete" % (kind, k))
                continue
            a, b, c = (check_arm(pr["4k"], kind), check_arm(pr["thp"], kind),
                       check_arm(pr["default"], kind))
            row = {"pair": k, "ns_per_op_4k": a, "ns_per_op_thp": b, "ns_per_op_default": c,
                   "ratio_4k_over_thp": a / b, "ratio_default_over_thp": c / b, "ratio_4k_over_default": a / c,
                   "online_ms_4k": float(pr["4k"]["parsed"]["fields"]["online_ms"]),
                   "online_ms_thp": float(pr["thp"]["parsed"]["fields"]["online_ms"]),
                   "online_ms_default": float(pr["default"]["parsed"]["fields"]["online_ms"]),
                   "setup_ms_4k": float(pr["4k"]["parsed"]["fields"]["setup_ms"]),
                   "setup_ms_thp": float(pr["thp"]["parsed"]["fields"]["setup_ms"]),
                   "setup_ms_default": float(pr["default"]["parsed"]["fields"]["setup_ms"]),
                   "max_anon_huge_kb": {m: pr[m]["parsed"].get("pages", {}).get("max_anon_huge_kb") for m in pr},
                   "contention_flags": {m: pr[m]["noise"] for m in pr}}
            if kind == "ic":
                for m in ("4k", "thp"):
                    if (k, m) in nulls:
                        row["pchase_ns_%s" % m] = nulls[(k, m)]
                        row["ic_over_pchase_%s" % m] = row["ns_per_op_%s" % m] / nulls[(k, m)]
            out.append(row)
            logs.append(math.log(a / b))
        g, ci = tint(logs)
        sec = {}
        for key in ("ratio_default_over_thp", "ratio_4k_over_default"):
            vals = [math.log(r[key]) for r in out]
            sec[key] = tint(vals) if vals else (None, [None, None])
        return out, g, ci, sec

    ic_rows, r_ic, ci_ic, sec_ic = panel("ic")
    rho_rows, r_rho, ci_rho, sec_rho = panel("rho")
    eligible = not issues and len(ic_rows) == protocol["ic_panel"]["pairs"] and len(rho_rows) == protocol["rho_panel"]["pairs"]
    if not eligible or ci_ic[0] is None:
        ic_reading = rho_reading = "no_result"
    else:
        lo, hi = ci_ic
        if r_ic >= 1.5 and lo > 1:
            ic_reading = "thp_cuts_ic_ns_per_probe_ge_1.5x"
        elif lo > 1:
            ic_reading = "thp_cuts_ic_ns_per_probe_below_1.5x"
        elif 0.9 <= lo and hi <= 1.1:
            ic_reading = "thp_change_under_10pct"
        elif hi < 1:
            ic_reading = "thp_slows_ic"
        else:
            ic_reading = "not_separated"
        lo, hi = ci_rho
        if 0.95 <= lo and hi <= 1.05:
            rho_reading = "rho_change_under_5pct"
        elif (lo > 1 or hi < 1):
            rho_reading = "rho_changed"
        else:
            rho_reading = "not_resolved"
    ic_on = {m: st.fmean(r["online_ms_%s" % m] for r in ic_rows) for m in ("4k", "default", "thp")} if ic_rows else {}
    rho_on = {m: st.fmean(r["online_ms_%s" % m] for r in rho_rows) for m in ("4k", "default", "thp")} if rho_rows else {}
    result = {
        "smoke": smoke, "eligible": eligible, "issues": issues,
        "ic": {"pairs": ic_rows, "R_4k_over_thp": r_ic, "ci95_t": ci_ic, "reading": ic_reading,
               "mean_online_ms": ic_on, "secondary": sec_ic},
        "rho": {"pairs": rho_rows, "R_4k_over_thp": r_rho, "ci95_t": ci_rho, "reading": rho_reading,
                "mean_online_ms": rho_on, "secondary": sec_rho},
        "gap_to_tuned_rho_on_q0": {m: (rho_on[m] / ic_on[m]) for m in ic_on} if ic_on and rho_on else None,
        "idea_prediction_4_met": ic_reading == "thp_cuts_ic_ns_per_probe_ge_1.5x" and rho_reading == "rho_change_under_5pct",
        "pointer_chase_sweep": sweep_out,
    }
    (receipt / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    f = lambda v: "n/a" if v is None else ("%.4g" % v)
    lines = ["| quantity | value |", "| --- | --- |",
             "| smoke (not evidence) | %s |" % smoke, "| eligible | %s |" % eligible,
             "| IC ns/probe 4k / thp, geometric mean [95%% t] | %s [%s, %s] -> %s |" % (f(r_ic), f(ci_ic[0]), f(ci_ic[1]), ic_reading),
             "| rho ns/step 4k / thp [95%% t] | %s [%s, %s] -> %s |" % (f(r_rho), f(ci_rho[0]), f(ci_rho[1]), rho_reading),
             "| IC default / thp; 4k / default | %s; %s |" % (f(sec_ic["ratio_default_over_thp"][0]), f(sec_ic["ratio_4k_over_default"][0])),
             "| mean IC online ms 4k / default / thp | %s / %s / %s |" % (f(ic_on.get("4k")), f(ic_on.get("default")), f(ic_on.get("thp"))),
             "| mean rho online ms 4k / default / thp | %s / %s / %s |" % (f(rho_on.get("4k")), f(rho_on.get("default")), f(rho_on.get("thp"))),
             "| idea prediction 4 met | %s |" % result["idea_prediction_4_met"]]
    for x in sweep_out:
        lines.append("| pchase %d B %s ns/access | %s (x%s of 4k) |" % (x["size_bytes"], x["mode"], f(x["ns_per_access"]), f(x.get("over_4k"))))
    lines.append("| issues | %s |" % ("; ".join(issues) if issues else "none"))
    (receipt / "result_table.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"eligible": eligible, "ic_reading": ic_reading, "rho_reading": rho_reading,
                      "R_ic": r_ic, "R_rho": r_rho, "issues": len(issues)}))


if __name__ == "__main__":
    main()
