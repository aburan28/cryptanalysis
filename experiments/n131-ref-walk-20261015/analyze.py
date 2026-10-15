#!/usr/bin/env python3
"""Decision rules of protocol.json applied to one run directory.

  analyze.py <run_dir>     writes <run_dir>/analysis.json and prints analysis.txt
"""
import json
import math
import random
import re
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = json.loads((HERE / "protocol.json").read_text())
CONST = json.loads((HERE / "inputs/constants.json").read_text())
CYCLES_2009 = {"single_core": 529, "per_core_four_cores": 534, "clock_ghz": 2.997,
               "cpu": "Core 2 Extreme Q6850", "source": "ePrint 2009/541 sec. 4",
               "pdf": "crypto-autoresearcher:inputs/BAILEY-2009-541-ECC2K130/ecc2k130-2009-541.pdf",
               "pdf_sha256": "825f19a11b489ee8ed844cf026e6ebbd08d8ad93eadb192e72a8e411a73bf2a4"}


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def boot(stat, n, draws, seed):
    rng = random.Random(seed)
    vals = sorted(stat([rng.randrange(n) for _ in range(n)]) for _ in range(draws))
    q = lambda a: vals[min(len(vals) - 1, int(a * len(vals)))]
    return {"ci95": [q(0.025), q(0.975)], "ci99_bonf5": [q(0.001), q(0.999)]}


def timing(run, n):
    rows = [r for r in jl(run / f"timing_n{n}.jsonl") if not r["warmup"]]
    arms = PROTO["timing"]["arms"]
    by = {a: {r["round"]: r for r in rows if r["arm"] == a} for a in arms}
    rounds = sorted(by[arms[0]])
    det = {a: len({r["checksum"] for r in by[a].values()}) == 1 for a in arms}
    seed = 2026101531
    out = {"rounds": len(rounds), "deterministic_checksums": det,
           "aa_checksums_equal": {"bailey": by["bailey"][rounds[0]]["checksum"] == by["bailey_aa"][rounds[0]]["checksum"],
                                  "canon": by["canon"][rounds[0]]["checksum"] == by["canon_aa"][rounds[0]]["checksum"]},
           "ns_per_step": {}, "ratios": {}, "events_per_step": {}}
    for a in arms:
        v = [by[a][k]["ns_per_step"] for k in rounds]
        lg = [math.log(x) for x in v]
        gm = math.exp(sum(lg) / len(lg))
        b = boot(lambda idx: math.exp(sum(lg[i] for i in idx) / len(idx)), len(lg), 20000, seed)
        r0 = by[a][rounds[0]]
        out["ns_per_step"][a] = {"geomean": gm, **b, "min": min(v), "max": max(v)}
        out["events_per_step"][a] = {k: r0[k] / r0["lane_steps"] for k in ("dps", "escapes", "restarts", "zero_den")}
    def ratio(x, y):
        lg = [math.log(by[x][k]["ns_per_step"] / by[y][k]["ns_per_step"]) for k in rounds]
        est = math.exp(sum(lg) / len(lg))
        b = boot(lambda idx: math.exp(sum(lg[i] for i in idx) / len(idx)), len(lg), 20000, seed)
        return {"estimate": est, **b}
    for x, y in [("bailey_aa", "bailey"), ("canon_aa", "canon"), ("canon_exh", "canon"), ("bailey", "canon"),
                 ("canon_null", "canon"), ("canon_nolift", "canon"), ("bailey_nodpc", "bailey")]:
        out["ratios"][f"{x}/{y}"] = ratio(x, y)
    R = out["ratios"]
    share = lambda k: {"estimate": 1 - R[k]["estimate"], "ci95": [1 - R[k]["ci95"][1], 1 - R[k]["ci95"][0]]}
    out["shares"] = {"canonicalization_whole (1 - canon_null/canon)": share("canon_null/canon"),
                     "lift_scan_alone (1 - canon_nolift/canon)": share("canon_nolift/canon"),
                     "bailey_at_dp_canonicalization (1 - bailey_nodpc/bailey)": share("bailey_nodpc/bailey")}
    aa_ok = all(0.97 <= R[k]["estimate"] <= 1.03 and R[k]["ci95"][0] <= 1 <= R[k]["ci95"][1]
                for k in ("bailey_aa/bailey", "canon_aa/canon"))
    pc_ok = R["canon_exh/canon"]["ci95"][0] > 1
    out["gates"] = {"aa": "pass" if aa_ok else "harness noisy", "positive_control": "pass" if pc_ok else "invalid",
                    "checksums": "pass" if all(det.values()) and all(out["aa_checksums_equal"].values()) else "FAIL"}
    out["valid"] = aa_ok and pc_ok and out["gates"]["checksums"] == "pass"
    return out


def ir(run):
    rows = json.loads((run / "ir.json").read_text())
    out = {}
    for n in (131, 83):
        d = {r["arm"]: r["ir_per_step"] for r in rows if r["n"] == n}
        out[str(n)] = {"ir_per_step": d,
                       "bailey/canon": d["bailey"] / d["canon"],
                       "share_canonicalization_whole": 1 - d["canon_null"] / d["canon"],
                       "share_lift_scan": 1 - d["canon_nolift"] / d["canon"],
                       "share_bailey_at_dp": 1 - d["bailey_nodpc"] / d["bailey"],
                       "aa_bailey": d["bailey_aa"] / d["bailey"], "aa_canon": d["canon_aa"] / d["canon"]}
    return out


def heuristics():
    pj = [0.0] * 8
    for w in range(1, 84, 2):
        pj[(w >> 1) & 7] += comb(83, w) / 2 ** 82
    f = lambda s: 1 / math.sqrt(1 - s)
    return {"bailey_pj": pj, "bailey": f(sum(p * p for p in pj)), "canon32": f(1 / 32), "canon8": f(1 / 8),
            "canon32_noneg": math.sqrt(2) * f(1 / 32)}


def completion(run):
    rows = jl(run / "panel_solves.jsonl")
    arms = PROTO["completion"]["arms"]
    out = {"rows": len(rows), "unverified": sum(1 for r in rows if not r["verified"]), "per_arm": {}, "ratios": {}}
    by = {a: {} for a in arms}
    for r in rows:
        by[r["arm"]].setdefault(r["target"], {})[r["seed_index"]] = r
    targets = sorted(by[arms[0]])
    seed = 2026101583
    def m(a, t, seeds=(0, 1)):
        return sum(by[a][t][s]["steps_over_floor"] for s in seeds) / len(seeds)
    for a in arms:
        v = [m(a, t) for t in targets]
        b = boot(lambda idx: sum(v[i] for i in idx) / len(idx), len(v), 20000, seed)
        rr = [x for t in targets for x in by[a][t].values()]
        out["per_arm"][a] = {"solves": len(rr), "verified": sum(x["verified"] for x in rr),
                             "mean_steps_over_floor": sum(v) / len(v), **b,
                             "median_steps_over_floor": sorted(x["steps_over_floor"] for x in rr)[len(rr) // 2],
                             "escapes_per_step": sum(x["escapes"] for x in rr) / sum(x["steps"] for x in rr),
                             "dps_per_step": sum(x["dps"] for x in rr) / sum(x["steps"] for x in rr),
                             "restarts": sum(x["restarts"] for x in rr),
                             "failed_collisions": sum(x["failed_collisions"] for x in rr),
                             "mean_table_entries": sum(x["table"] for x in rr) / len(rr),
                             "table_bytes_model": "entries x 48 B (24 B key + two 8 B logs + 8 B lane), HashMap overhead excluded"}
    def ratio(x, y):
        vx = [m(x, t) for t in targets]
        vy = [m(y, t) for t in targets]
        est = sum(vx) / sum(vy)
        b = boot(lambda idx: sum(vx[i] for i in idx) / sum(vy[i] for i in idx), len(targets), 20000, seed)
        return {"estimate": est, **b}
    for x, y in [("bailey", "canon32"), ("canon8", "canon32"), ("canon32_noneg", "canon32"), ("bailey", "canon8")]:
        out["ratios"][f"{x}/{y}"] = ratio(x, y)
    for a in ("bailey", "canon32"):
        v0 = [m(a, t, (0,)) for t in targets]
        v1 = [m(a, t, (1,)) for t in targets]
        b = boot(lambda idx: sum(v0[i] for i in idx) / sum(v1[i] for i in idx), len(targets), 20000, seed)
        out["ratios"][f"AA {a} seed0/seed1"] = {"estimate": sum(v0) / sum(v1), **b}
    pc = out["ratios"]["canon32_noneg/canon32"]
    aa = all(out["ratios"][f"AA {a} seed0/seed1"]["ci95"][0] <= 1 <= out["ratios"][f"AA {a} seed0/seed1"]["ci95"][1]
             for a in ("bailey", "canon32"))
    out["gates"] = {"all_verified": out["unverified"] == 0, "positive_control": "pass" if pc["ci95"][0] > 1 else "invalid",
                    "aa": "pass" if aa else "fail"}
    out["valid"] = out["unverified"] == 0 and pc["ci95"][0] > 1
    out["heuristic_predictions"] = heuristics()
    return out


def clocks(run):
    rec = json.loads((run / "receipt_pre.json").read_text())
    lscpu = rec.get("lscpu", "")
    mx = re.search(r"CPU max MHz:\s*([\d.]+)", lscpu)
    mhz = [float(x) for x in rec.get("cpu_mhz", []) if re.match(r"^[\d.]+$", x)]
    model = rec.get("cpu_model")
    nominal = re.search(r"@\s*([\d.]+)GHz", model or "")
    return {"cpu_model": model, "cpu_mhz_reported": mhz[:4],
            "nominal_ghz": float(nominal.group(1)) if nominal else (mhz[0] / 1000 if mhz else None),
            "max_ghz": float(mx.group(1)) / 1000 if mx else None}


def main():
    run = Path(sys.argv[1])
    a = {"protocol_sha256": __import__("hashlib").sha256((HERE / "protocol.json").read_bytes()).hexdigest()}
    ex = json.loads((run / "exactness.json").read_text())
    a["exactness_pass"] = ex["pass"]
    a["timing"] = {str(n): timing(run, n) for n in (131, 83)}
    a["ir"] = ir(run) if (run / "ir.json").exists() else None
    a["completion"] = completion(run)
    ck = run / "independent_check_panel.json"
    a["independent_check_panel"] = json.loads(ck.read_text()) if ck.exists() else None
    clk = clocks(run)
    a["clock"] = clk
    T = a["timing"]
    a["n131_over_n83_ns_per_step"] = {d: T["131"]["ns_per_step"][d]["geomean"] / T["83"]["ns_per_step"][d]["geomean"]
                                      for d in ("bailey", "canon")}
    cyc = {}
    for d in ("bailey", "canon"):
        ns = T["131"]["ns_per_step"][d]["geomean"]
        cyc[d] = {"ns_per_step": ns,
                  "cycles_at_nominal": ns * clk["nominal_ghz"] if clk["nominal_ghz"] else None,
                  "cycles_at_max": ns * clk["max_ghz"] if clk["max_ghz"] else None}
    a["cycles_per_iteration_n131"] = {"this_run": cyc, "ecc2k130_2009": CYCLES_2009,
                                      "note": "side by side, not divided: different machines, clocks and code; "
                                              "the runner's clock under load is not observable"}
    r131 = int(CONST["131"]["r"])
    floor131 = math.sqrt(math.pi * r131 / (4 * 131))
    comp = {}
    C = a["completion"]["per_arm"]
    for d, pen in (("bailey", "bailey"), ("canon", "canon32")):
        ns = T["131"]["ns_per_step"][d]["geomean"]
        p = C[pen]["mean_steps_over_floor"]
        comp[d] = {"ns_per_step_n131": ns, "steps_over_floor_n83": p, "floor_n131": floor131,
                   "log2_floor_n131": math.log2(floor131), "log2_steps": math.log2(floor131 * p),
                   "core_years": ns * p * floor131 * 1e-9 / (365.25 * 86400)}
    a["model_composition"] = {"label": "MODEL COMPOSITION (not a measurement): ns/step at n=131 x steps/floor "
                                       "measured at n=83 x floor(131); transfers only under heuristic H1",
                              "per_design": comp,
                              "ratio_bailey_over_canon": (comp["bailey"]["ns_per_step_n131"] * comp["bailey"]["steps_over_floor_n83"])
                              / (comp["canon"]["ns_per_step_n131"] * comp["canon"]["steps_over_floor_n83"])}
    (run / "analysis.json").write_text(json.dumps(a, indent=1))
    L = []
    t = T["131"]
    L.append(f"exactness gate: {'pass' if a['exactness_pass'] else 'FAIL'}")
    for n in ("131", "83"):
        tt = T[n]
        L.append(f"n={n} timing gates {tt['gates']}")
        for arm, v in tt["ns_per_step"].items():
            L.append(f"  {arm:14s} {v['geomean']:9.2f} ns/step [{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}]")
        for k, v in tt["ratios"].items():
            L.append(f"  {k:22s} {v['estimate']:.4f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}]")
        for k, v in tt["shares"].items():
            L.append(f"  share {k}: {v['estimate']:.4f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}]")
    c = a["completion"]
    L.append(f"completion: {c['rows']} solves, unverified {c['unverified']}, gates {c['gates']}")
    for arm, v in c["per_arm"].items():
        L.append(f"  {arm:14s} steps/floor {v['mean_steps_over_floor']:.4f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}] "
                 f"escapes/step {v['escapes_per_step']:.5f}")
    for k, v in c["ratios"].items():
        L.append(f"  {k:28s} {v['estimate']:.4f} [{v['ci95'][0]:.4f}, {v['ci95'][1]:.4f}]")
    L.append(f"heuristic predictions {json.dumps({k: v for k, v in c['heuristic_predictions'].items() if k != 'bailey_pj'})}")
    L.append(f"n131/n83 ns per step: {a['n131_over_n83_ns_per_step']}")
    L.append(f"cycles/iteration at n=131: {json.dumps(cyc)}; 2009: 529 (1 core) / 534 (4 cores)")
    L.append(a["model_composition"]["label"])
    for d, v in comp.items():
        L.append(f"  {d}: log2 steps {v['log2_steps']:.3f}, {v['core_years']:.4g} core-years at this run's ns/step")
    txt = "\n".join(L)
    (run / "analysis.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
