import json, statistics as st, sys
D = json.load(open("results.json")); rows = D["rows"]
def ops(r, w): return r["group"] + w * (r["lookup"] + r["la"])
def mean(row, s, w=1): return st.mean(ops(r, w) for r in row[s])
out = {}
for pool in (1000, 2000):
    R = rows[:pool]; o = {}
    for s in ("factor_base", "bsgs", "rho"):
        for w in (0, 0.1, 1):
            ms = [mean(r, s, w) for r in R]
            best = min(range(pool), key=lambda i: (ms[i], i))
            start = [i for i in range(pool) if R[i]["steps"] == 0]
            o[f"{s}@w={w}"] = dict(
                min=min(ms), max=max(ms), avg=st.mean(ms),
                solve_min=min(ops(x, w) for r in R for x in r[s]),
                solve_max=max(ops(x, w) for r in R for x in r[s]),
                best=dict((k, R[best][k]) for k in ("idx", "A", "B", "j", "path", "steps", "inverse_pairs", "u")),
                start_best=min(ms[i] for i in start), n_start=len(start))
    o["distinct_models"] = len({(r["A"], r["B"]) for r in R})
    o["distinct_j"] = sorted({r["j"] for r in R})
    out[pool] = o
json.dump(out, open("summary.json", "w"), indent=1)
for pool, o in out.items():
    print(f"== pool {pool}: {o['distinct_models']} distinct models, j in {o['distinct_j']}")
    for k, v in o.items():
        if "@" in k:
            print(f"{k:18s} cand-mean min {v['min']:8.2f} max {v['max']:8.2f} avg {v['avg']:8.2f} | solves {v['solve_min']:.1f}-{v['solve_max']:.1f} | start-curve best {v['start_best']:.2f} | best {v['best']}")
