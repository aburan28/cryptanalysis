"""PDP (m=3) Groebner-basis difficulty on toy Koblitz classes: E0 (b=1) vs floor curves
(level-l CM curves isogenous to E0) vs random Tr-matched b.  Uses the pdp-scaling Weil
descent (copied here) and msolve -v 2; records machine-independent F4 statistics
(max step degree, largest matrix, #rows reduced, #pairs) plus CPU time.
Every solution is re-verified on points (verify_solution)."""
import json, os, re, subprocess, sys, tempfile, time, random
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from descend import make_instance, verify_solution
from solve import _msolve_poly, _parse_msolve_basis

def run_one(job):
    n, m, l, seed, kind, idx, b = job
    inst = make_instance(n, m, l, seed, b=b)
    nv = inst.nvars; eqs = inst.equations()
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.ms"); out = os.path.join(d, "out.ms")
        with open(inp, "w") as fh:
            fh.write(",".join(f"v{j}" for j in range(nv)) + "\n2\n")
            polys = ["+".join(_msolve_poly(mk, nv) for mk in sorted(eq)) for eq in eqs if eq]
            polys += [f"v{j}^2+v{j}" for j in range(nv)]
            fh.write(",\n".join(polys) + "\n")
        t0 = os.times()
        try:
            r = subprocess.run(["msolve", "-g", "2", "-v", "2", "-t", "1", "-f", inp, "-o", out],
                               capture_output=True, text=True, timeout=1500)
        except subprocess.TimeoutExpired:
            return dict(n=n, m=m, l=l, seed=seed, kind=kind, idx=idx, b=b, status="timeout")
        t1 = os.times()
        cpu = (t1.children_user - t0.children_user) + (t1.children_system - t0.children_system)
        text = open(out).read()
    degs, rowsred = [], None
    for line in r.stdout.splitlines():
        mm = re.match(r"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) x (\d+)\s", line)
        if mm:
            degs.append((int(mm.group(1)), int(mm.group(4)), int(mm.group(5))))
    def grab(key):
        mm = re.search(key + r"\s+(\d+)", r.stdout)
        return int(mm.group(1)) if mm else None
    basis = _parse_msolve_basis(text)
    fixed = {}
    for p in basis:
        terms = [t.strip() for t in p.replace("-", "+").split("+") if t.strip()]
        vs = [t for t in terms if t.startswith("1*v") and "^1" in t and "*v" not in t[3:]]
        consts = [t for t in terms if t == "1"]
        if len(vs) == 1 and len(terms) == len(vs) + len(consts):
            fixed[int(vs[0][3:].split("^")[0])] = len(consts) % 2
    free = [j for j in range(nv) if j not in fixed]
    nsol_verified = 0
    if len(free) <= 16:
        base = sum(c << j for j, c in fixed.items())
        for k in range(1 << len(free)):
            v = base
            for i, j in enumerate(free):
                if (k >> i) & 1: v |= 1 << j
            if inst.evaluate(v) == 0 and verify_solution(inst, v):
                nsol_verified += 1
    return dict(n=n, m=m, l=l, seed=seed, kind=kind, idx=idx, b=b, status="ok", cpu=cpu,
                max_step_deg=max(d for d, _, _ in degs) if degs else None,
                max_matrix_rows=max(a for _, a, _ in degs) if degs else None,
                max_matrix_cols=max(c for _, _, c in degs) if degs else None,
                n_steps=len(degs), rows_reduced=grab(r"#rows reduced"),
                pairs_reduced=grab(r"#pairs reduced"), zero_red=grab(r"#zero reductions"),
                basis_size=len(basis), free_vars=len(free), verified_solutions=nsol_verified)

if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    outp = sys.argv[2]
    ls = [int(x) for x in sys.argv[3].split(",")]
    seeds = [int(x) for x in sys.argv[4].split(",")]
    nper = int(sys.argv[5])
    jobs = []
    for nk, d in data.items():
        n = d["n"]
        rng = random.Random(7 + n)
        fl = rng.sample(range(len(d["floor"])), nper)
        curves = [("E0", 0, 1)] + [("floor", i, d["floor"][i]["b"]) for i in fl] + \
                 [("control", i, d["controls"][i]["b"]) for i in range(nper)]
        for l in ls:
            for s in seeds:
                for kind, i, b in curves:
                    jobs.append((n, 3, l, s, kind, i, b))
    done = set()
    if os.path.exists(outp):
        for line in open(outp):
            r = json.loads(line); done.add((r["n"], r["m"], r["l"], r["seed"], r["kind"], r["idx"]))
    jobs = [j for j in jobs if (j[0], j[1], j[2], j[3], j[4], j[5]) not in done]
    print("jobs", len(jobs), flush=True)
    with Pool(int(os.environ.get("NPROC", "6"))) as pool, open(outp, "a") as fh:
        for r in pool.imap_unordered(run_one, jobs):
            fh.write(json.dumps(r) + "\n"); fh.flush()
            print(r["n"], r["l"], r["seed"], r["kind"], r["idx"], r.get("cpu"), r.get("max_step_deg"),
                  r.get("rows_reduced"), r.get("verified_solutions"), flush=True)
