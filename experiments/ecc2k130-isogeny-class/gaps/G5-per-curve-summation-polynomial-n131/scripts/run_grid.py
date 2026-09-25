"""G5 grid: one job = (group, curve, subspace, k).  Within a job, for m = 2 and 3:
  plain system, 10 random N-subgroup targets + 5 planted targets (sum of m factor-base points,
  in the odd-order subgroup);  codex system (m = 3), 10 image targets (Codex's exact image) +
  the same 10 random targets.
Each system gets: descended-system statistics, the exact solution set (brute force),
Codex's formal d_reg after row reduction (Singular std; cap 600 s), optionally the raw
(no row reduction) formal d_reg, and msolve F4 (cap 600 s).
Output: raw/grid/<jobid>.jsonl (atomic, one file per job; existing files are skipped).

Usage: sage -python run_grid.py --shard I --nshards W [--budget SECONDS] [--only JOBID,...]
       sage -python run_grid.py --list
"""
import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402

OUT = ROOT / "raw" / "grid"
OUT.mkdir(parents=True, exist_ok=True)
CTRL = json.loads((ROOT / "controls.json").read_text())
KS = (4, 5, 6)
N_RAND, N_PLANT, N_IMG = 10, 5, 10          # main group (E0, A000, B000, A010)
N_RAND_C, N_PLANT_C, N_IMG_C = 5, 3, 5       # control groups (machine shared, load ~40)
CAP_FORMAL, CAP_MSOLVE, CAP_RAW = 600, 600, 120


def curve_b(label):
    if label in L.ecc2k.RECORDS:
        return int(L.ecc2k.RECORDS[label]["b_int"]), L.ecc2k.CARD
    for c in CTRL["curves"]:
        if c["label"] == label:
            return int(c["b_int"]), int(c["order"])
    raise KeyError(label)


def subspace_basis(kind, idx, k, b):
    if kind == "poly":
        return L.poly_basis(k)
    if kind == "rand":
        return [L.dec(u) for u in CTRL["random_bases"][idx][:k]]
    if kind == "scaled":
        c = L.dec(CTRL["scale_constants"][idx])
        return [c * L.ZGEN**j for j in range(k)]
    if kind == "powerw":
        w = L.dec(CTRL["power_w"][idx])
        return [w**j for j in range(k)]
    if kind == "powerb":  # span{1, b, .., b^(k-1)}: the curve's own b as the power generator
        return [b**j for j in range(k)]
    if kind == "shiftb":  # span{1, w, .., w^(k-1)} with w = b + 1, so that b = 1 + w (like b = 1+z)
        w = b + 1
        return [w**j for j in range(k)]
    raise ValueError(kind)


def jobs():
    J = []
    for lab in ("E0", "A000", "B000", "A010"):
        J.append(("main", lab, "poly", 0))
    for lab in ("E0", "A000"):
        for s in range(5):
            J.append(("randsub", lab, "rand", s))
    for s in range(3):
        J.append(("scaled", "E0", "scaled", s))
    for s in range(3):
        J.append(("scaled", "A000", "scaled", s))
    for c in CTRL["curves"]:
        J.append(("randcurve_" + c["kind"], c["label"], "poly", 0))
    for s in range(3):
        J.append(("powerw", "E0", "powerw", s))
    for lab in ("A000", "B000", "A010"):
        J.append(("powerb", lab, "powerb", 0))
    for lab in ("RD00", "RD01"):
        for s in range(2):
            J.append(("randsub_dense", lab, "rand", s))
    for lab in ("A000", "B000", "A010", "RD00"):
        J.append(("shiftb", lab, "shiftb", 0))
    out = []
    for g, lab, kind, idx in J:
        for k in KS:
            out.append({"group": g, "label": lab, "sub": kind, "sub_idx": idx, "k": k,
                        "id": f"{g}__{lab}__{kind}{idx}__k{k}"})
    return out


def measure(C, basis, k, m, mode, tkind, tidx, R, dom, extra, raw_formal, caps=None):
    cap_formal, cap_msolve = caps or (CAP_FORMAL, CAP_MSOLVE)
    nv = m * k
    t0 = time.process_time()
    anf = L.descended_anf(m, basis, C.b, R[0])
    t_desc = time.process_time() - t0
    row = {"m": m, "mode": mode, "target_kind": tkind, "target_idx": tidx,
           "target_x": str(L.enc(R[0])), "nv": nv, "descent_cpu": t_desc,
           "anf_monomials": len(anf), "anf_degree": L.anf_degree(anf),
           "desc_rank": L.coeff_rank(anf)}
    row.update(extra)
    allowed = set(dom["lifts"])
    gens, nd = L.build_generators(anf, nv, k, m, mode, allowed)
    row["n_desc_eqs_nonzero"] = nd
    row["n_generators"] = len(gens)
    sols = L.solutions_bruteforce(anf, nv)
    kmask = (1 << k) - 1
    if mode == "codex":
        sols = [a for a in sols if all(((a >> (i * k)) & kmask) in allowed for i in range(m))
                and len({(a >> (i * k)) & kmask for i in range(m)}) == m]
    row["bf_solutions"] = len(sols)
    if sols and len(sols) <= 200:
        row["solution_classes"] = L.classify_solutions(C, basis, m, sols, R)
    fr = L.formal_regularity(gens, nv, cap_formal, reduce_first=True)
    row["formal"] = fr
    if raw_formal:
        row["formal_raw"] = L.formal_regularity(gens, nv, CAP_RAW, reduce_first=False)
    ms, gb = L.run_msolve(gens, nv, cap_msolve, f"{C.label}{k}{m}{mode}{tkind}{tidx}{row['target_x']}")
    if gb is not None:
        cnt, ok = L.gb_solution_count(gb, nv, sols[:50])
        ms["solution_count"] = cnt
        ms["gb_vanishes_on_bf_solutions"] = ok
        ms["agrees_with_bruteforce"] = cnt == len(sols) and ok
    row["msolve"] = ms
    return row


def run_job(job):
    lab, k = job["label"], job["k"]
    b_int, order = curve_b(lab)
    C = L.CurveCtx(lab, L.dec(b_int), order=order)
    basis = subspace_basis(job["sub"], job["sub_idx"], k, C.b)
    assert L.is_independent(basis)
    t0 = time.time()
    dom = L.factor_domain(C, basis)
    base = {**{x: job[x] for x in ("id", "group", "label", "sub", "sub_idx", "k")},
            "b_int": str(b_int), "trace_b": L.ftrace(C.b), "hw_b": bin(b_int).count("1"),
            "basis_int": [str(L.enc(u)) for u in basis], "x_count": len(dom["lifts"]),
            "odd_subgroup_targets": C.two_part_is_z4, "two_part": C.two}
    rows = []
    raw_formal = k <= 4
    main = job["group"] == "main"
    n_rand, n_plant, n_img = (N_RAND, N_PLANT, N_IMG) if main else (N_RAND_C, N_PLANT_C, N_IMG_C)
    # random subspaces at k = 6: a probe (E0, rand0) hit the 300 s caps for both the formal d_reg and
    # msolve, so m = 3 is limited to 1 random + 1 planted (plain) and 1 image target (codex).
    n_rand3, n_plant3, n_img3, n_rand_codex = n_rand, n_plant, n_img, n_rand
    caps = None
    if job["group"].startswith("randsub") and k == 6:
        n_rand3, n_plant3, n_img3, n_rand_codex = 1, 1, 1, 0
        caps = (300, 300)  # keeps the whole job inside one 2400 s command
    rand_targets = []
    for i in range(n_rand):
        rng = random.Random(L.seed_int("G5", lab, "rand", i))
        rand_targets.append(C.random_odd_target(rng))
    for m in (2, 3):
        for i, R in enumerate(rand_targets[: (n_rand if m == 2 else n_rand3)]):
            rows.append({**base, **measure(C, basis, k, m, "plain", "random", i, R, dom, {}, raw_formal,
                                           caps if m == 3 else None)})
        for i in range(n_plant if m == 2 else n_plant3):
            rng = random.Random(L.seed_int("G5", job["id"], m, "planted", i))
            pt = L.planted_target(C, dom, m, rng, odd_only=C.two_part_is_z4)
            if pt is None:
                rows.append({**base, "m": m, "mode": "plain", "target_kind": "planted",
                             "target_idx": i, "status": "no_planted_target"})
                continue
            R, tri = pt
            rows.append({**base, **measure(C, basis, k, m, "plain", "planted", i, R, dom,
                                           {"planted_masks": tri}, raw_formal, caps if m == 3 else None)})
    m = 3
    img = L.enumerate_image(dom, m, odd_only=C.two_part_is_z4)
    keys = sorted(img)
    rng = random.Random(L.seed_int("G5", job["id"], "image"))
    pick = rng.sample(keys, min(n_img, len(keys)))[:n_img3]
    for i, key in enumerate(pick):
        R = C.E(L.dec(key[0]), L.dec(key[1]))
        rows.append({**base, "image_size": len(img),
                     **measure(C, basis, k, m, "codex", "image", i, R, dom,
                               {"expected_solutions": 6 * len(img[key])}, raw_formal, caps)})
    for i, R in enumerate(rand_targets[:n_rand_codex]):
        rows.append({**base, "image_size": len(img),
                     **measure(C, basis, k, m, "codex", "random", i, R, dom, {}, raw_formal)})
    for r in rows:
        r["job_seconds"] = time.time() - t0
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--budget", type=float, default=2000)
    ap.add_argument("--only", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--groups", default="", help="comma list of groups to run (default all)")
    ap.add_argument("--exclude-groups", default="")
    ap.add_argument("--ks", default="", help="comma list of k to run (default all)")
    a = ap.parse_args()
    J = jobs()
    if a.list:
        for j in J:
            print(j["id"], "done" if (OUT / (j["id"] + ".jsonl")).exists() else "todo")
        print(len(J), "jobs")
        return
    if a.only:
        want = set(a.only.split(","))
        J = [j for j in J if j["id"] in want]
    if a.groups:
        J = [j for j in J if j["group"] in set(a.groups.split(","))]
    if a.ks:
        J = [j for j in J if j["k"] in {int(x) for x in a.ks.split(",")}]
    if a.exclude_groups:
        J = [j for j in J if j["group"] not in set(a.exclude_groups.split(","))]
    # heavy (k = 6) jobs spread over shards: interleave by k
    J = sorted(J, key=lambda j: (-j["k"], J.index(j)))
    mine = J[a.shard::a.nshards]
    start = time.time()
    for j in mine:
        path = OUT / (j["id"] + ".jsonl")
        if path.exists():
            continue
        if time.time() - start > a.budget:
            print("budget exhausted", flush=True)
            break
        t = time.time()
        try:
            rows = run_job(j)
        except Exception as exc:  # noqa: BLE001  record and continue with the next job
            import traceback
            (OUT / (j["id"] + ".error")).write_text(traceback.format_exc())
            print(j["id"], "ERROR", repr(exc), flush=True)
            continue
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
        os.replace(tmp, path)
        print(j["id"], len(rows), "rows", round(time.time() - t, 1), "s", flush=True)


if __name__ == "__main__":
    main()
