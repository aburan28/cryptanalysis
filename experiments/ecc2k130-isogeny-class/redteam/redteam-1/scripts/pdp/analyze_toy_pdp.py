import json, sys, random, statistics as st
rows = []
for f in sys.argv[2:]:
    rows += [json.loads(l) for l in open(f)]
rng = random.Random(1)
def perm_p(a, b, iters=20000):
    obs = abs(st.mean(a) - st.mean(b)); pool = a + b; k = len(a); c = 0
    for _ in range(iters):
        rng.shuffle(pool)
        if abs(st.mean(pool[:k]) - st.mean(pool[k:])) >= obs - 1e-12: c += 1
    return (c + 1) / (iters + 1)
out = {}
for n in sorted({r["n"] for r in rows}):
    for l in sorted({r["l"] for r in rows}):
        sub = [r for r in rows if r["n"] == n and r["l"] == l and r["status"] == "ok"]
        if not sub: continue
        cell = {}
        for kind in ("E0", "floor", "control"):
            ks = [r for r in sub if r["kind"] == kind]
            cell[kind] = dict(runs=len(ks),
                cpu_median=round(st.median(r["cpu"] for r in ks), 3),
                cpu_mean=round(st.mean(r["cpu"] for r in ks), 3),
                max_deg_values=sorted({r["max_step_deg"] for r in ks}),
                rows_reduced_mean=round(st.mean(r["rows_reduced"] for r in ks), 1),
                pairs_reduced_mean=round(st.mean(r["pairs_reduced"] for r in ks), 1),
                max_matrix_rows_mean=round(st.mean(r["max_matrix_rows"] for r in ks), 1),
                verified_solutions=sorted({r["verified_solutions"] for r in ks}))
        fl = [r for r in sub if r["kind"] == "floor"]; ct = [r for r in sub if r["kind"] == "control"]
        e0 = [r for r in sub if r["kind"] == "E0"]
        cell["perm_p_floor_vs_control"] = {k: round(perm_p([r[k] for r in fl], [r[k] for r in ct]), 4)
                                           for k in ("rows_reduced", "pairs_reduced", "max_matrix_rows", "cpu")}
        cell["perm_p_E0_vs_rest"] = {k: round(perm_p([r[k] for r in e0], [r[k] for r in fl + ct]), 4)
                                     for k in ("rows_reduced", "pairs_reduced", "cpu")}
        out[f"n{n}_l{l}"] = cell
        print(n, l, json.dumps(cell))
json.dump(out, open(sys.argv[1], "w"), indent=1)
