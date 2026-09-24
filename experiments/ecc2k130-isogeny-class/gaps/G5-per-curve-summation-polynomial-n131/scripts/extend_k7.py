"""Q1/Q5 extension beyond Codex's censored cells: k = 7 (21 variables) for m = 3.

(a) Codex's own k = 7 run-03 cells (E0 and A010 targets recorded by Codex; censored at 30 s
    there): codex-mode formal d_reg with a 600 s cap, plus msolve.
(b) plain m = 3 systems at k = 7 on the polynomial basis for E0, A000, B000, A010, 2 dense and
    2 sparse random curves: 3 random N-subgroup targets + 2 planted targets each; msolve (600 s)
    (no formal d_reg: it timed out at 600 s even on the two Codex k = 7 cells), brute-force count
    (2^21 assignments).
Usage: sage -python extend_k7.py PART  (PART = a | b:<label>)  -> raw/k7/*.json
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402

OUT = ROOT / "raw" / "k7"
OUT.mkdir(parents=True, exist_ok=True)
CTRL = json.loads((ROOT / "controls.json").read_text())
CAP = 600
k, m = 7, 3
nv = m * k


def curve(label):
    if label in L.ecc2k.RECORDS:
        return L.CurveCtx(label, L.dec(L.ecc2k.RECORDS[label]["b_int"]), order=L.ecc2k.CARD)
    c = next(c for c in CTRL["curves"] if c["label"] == label)
    return L.CurveCtx(label, L.dec(c["b_int"]), order=int(c["order"]))


def one(C, basis, dom, R, mode, tkind, tidx, extra=None, do_formal=True):
    t0 = time.process_time()
    anf = L.descended_anf(m, basis, C.b, R[0])
    row = {"label": C.label, "k": k, "m": m, "mode": mode, "target_kind": tkind, "target_idx": tidx,
           "target_x": str(L.enc(R[0])), "descent_cpu": time.process_time() - t0,
           "anf_monomials": len(anf), "desc_rank": L.coeff_rank(anf), **(extra or {})}
    allowed = set(dom["lifts"])
    gens, nd = L.build_generators(anf, nv, k, m, mode, allowed)
    sols = L.solutions_bruteforce(anf, nv)
    km = (1 << k) - 1
    if mode == "codex":
        sols = [a for a in sols if all(((a >> (i * k)) & km) in allowed for i in range(m))
                and len({(a >> (i * k)) & km for i in range(m)}) == m]
    row["bf_solutions"] = len(sols)
    ms, gb = L.run_msolve(gens, nv, CAP, f"k7{C.label}{mode}{tkind}{tidx}{row['target_x']}{basis[1]}")
    if gb is not None:
        cnt, ok = L.gb_solution_count(gb, nv, sols[:50])
        ms["solution_count"] = cnt
        ms["agrees_with_bruteforce"] = cnt == len(sols) and ok
    row["msolve"] = ms
    row["formal"] = (L.formal_regularity(gens, nv, CAP, reduce_first=True) if do_formal
                     else {"status": "not_run"})
    print(json.dumps({x: row[x] for x in ("label", "mode", "target_kind", "target_idx", "desc_rank",
                                          "bf_solutions")},) + " formal=" +
          json.dumps({x: row["formal"].get(x) for x in ("status", "d_reg", "top_quotient_dim", "std_cpu")}) +
          " msolve=" + json.dumps({x: ms.get(x) for x in ("status", "max_degree", "msolve_cpu_reported", "cpu")}),
          flush=True)
    return row


part = sys.argv[1]
basis = L.poly_basis(k)
if part == "a":
    CODEX7 = {"E0": "1461180299996937286368717225228383798326",
              "A010": "2454890327626404397084908531748247263751"}
    rows = []
    for lab, tx in CODEX7.items():
        C = curve(lab)
        dom = L.factor_domain(C, basis)
        img = L.enumerate_image(dom, m)
        seed = int.from_bytes(hashlib.sha256(f"{lab}:{k}:run03".encode()).digest(), "big")
        key = sorted(img)[seed % len(img)]
        R = C.E(L.dec(key[0]), L.dec(key[1]))
        rows.append(one(C, basis, dom, R, "codex", "codex_run03_target", 0,
                        {"image_size": len(img), "target_matches_codex": str(key[0]) == tx,
                         "x_count": len(dom["lifts"])}))
    (OUT / "codex_k7.json").write_text(json.dumps(rows, indent=1))
else:
    # b:<label>[:<sub>:<idx>]  with sub in poly | scaled | powerw | powerb | shiftb
    bits = part.split(":")
    lab = bits[1]
    sub, sidx = (bits[2], int(bits[3])) if len(bits) > 2 else ("poly", 0)
    C = curve(lab)
    if sub == "scaled":
        c = L.dec(CTRL["scale_constants"][sidx])
        basis = [c * L.ZGEN**j for j in range(k)]
    elif sub == "powerw":
        w = L.dec(CTRL["power_w"][sidx])
        basis = [w**j for j in range(k)]
    elif sub == "powerb":
        basis = [C.b**j for j in range(k)]
    elif sub == "shiftb":
        basis = [(C.b + 1)**j for j in range(k)]
    assert L.is_independent(basis)
    dom = L.factor_domain(C, basis)
    rows = []
    for i in range(3):
        R = C.random_odd_target(random.Random(L.seed_int("G5", lab, "rand", i)))
        rows.append(one(C, basis, dom, R, "plain", "random", i, do_formal=False))
    for i in range(2):
        R, tri = L.planted_target(C, dom, m, random.Random(L.seed_int("G5k7", lab, "planted", i)))
        rows.append(one(C, basis, dom, R, "plain", "planted", i, {"planted_masks": tri},
                        do_formal=False))
    for r in rows:
        r["sub"] = f"{sub}{sidx}"
        r["basis_int"] = [str(L.enc(u)) for u in basis]
    name = f"plain_k7_{lab}.json" if sub == "poly" else f"plain_k7_{lab}_{sub}{sidx}.json"
    (OUT / name).write_text(json.dumps(rows, indent=1))
