"""Independent check of the formal d_reg pipeline (no Singular): recompute the Hilbert function
of R/J, J = <top forms of the row-reduced generators> + <v_i^2>, by F_2 linear algebra in the
exterior-like algebra E = F_2[v]/(v_i^2) (dim (R/J)_d = C(n,d) - rank of the degree-d Macaulay
matrix of the squarefree top forms), and compare with the Singular-based values stored in the
grid rows.  Covers every main-group k = 4 m = 3 row (E0, A000, B000, A010; plain + codex) and
the k = 5 codex image rows of E0 and A010.
Usage: sage -python indep_hilbert.py  -> indep_hilbert.json"""
import itertools
import json
import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402


def hilbert_E(tops, n):
    """tops: list of sets of squarefree masks (homogeneous). Returns Hilbert function list."""
    tops = [t for t in tops if t]
    hf = []
    for d in range(n + 1):
        cols = [sum(1 << i for i in c) for c in itertools.combinations(range(n), d)]
        idx = {m: i for i, m in enumerate(cols)}
        piv = {}
        rank = 0
        for t in tops:
            e = bin(next(iter(t))).count("1")
            if e > d:
                continue
            for mc in itertools.combinations(range(n), d - e):
                mm = sum(1 << i for i in mc)
                row = 0
                for term in t:
                    if term & mm == 0:
                        row ^= 1 << idx[term | mm]
                while row:
                    p = row.bit_length() - 1
                    if p in piv:
                        row ^= piv[p]
                    else:
                        piv[p] = row
                        rank += 1
                        break
        hf.append(comb(n, d) - rank)
        if hf[-1] == 0:
            break
    while hf and hf[-1] == 0:
        hf.pop()
    return hf


out = []
for lab in ("E0", "A000", "B000", "A010"):
    for k in (4, 5):
        rows = [json.loads(l) for l in open(ROOT / "raw" / "grid" / f"main__{lab}__poly0__k{k}.jsonl")]
        C = L.CurveCtx(lab, L.dec(L.ecc2k.RECORDS[lab]["b_int"]), order=L.ecc2k.CARD)
        basis = L.poly_basis(k)
        dom = L.factor_domain(C, basis)
        for r in rows:
            if r["m"] != 3 or r["formal"].get("status") != "verified" or r["formal"]["d_reg"] == 0:
                continue
            if k == 5 and not (lab in ("E0", "A010") and r["mode"] == "codex" and r["target_kind"] == "image"):
                continue
            nv = 3 * k
            anf = L.descended_anf(3, basis, C.b, L.dec(r["target_x"]))
            gens, _ = L.build_generators(anf, nv, k, 3, r["mode"], set(dom["lifts"]))
            red = L.row_reduce(gens, nv)
            tops = []
            for g in red:
                t, d = L.top_form(g)
                if any(isinstance(mm, tuple) for mm in t):
                    continue  # v_i^2: zero in E
                tops.append(t)
            hf = hilbert_E(tops, nv)
            dreg = len(hf)  # = 1 + max degree with nonzero dimension
            rec = {"label": lab, "k": k, "mode": r["mode"], "target_kind": r["target_kind"], "target_idx": r["target_idx"],
                   "hf_independent": hf, "hf_singular": r["formal"]["hilbert_function"],
                   "d_reg_independent": dreg, "d_reg_singular": r["formal"]["d_reg"],
                   "match": hf == r["formal"]["hilbert_function"] and dreg == r["formal"]["d_reg"]}
            out.append(rec)
            print(json.dumps({x: rec[x] for x in ("label", "k", "mode", "target_kind", "target_idx", "d_reg_independent",
                                                  "d_reg_singular", "match")}), flush=True)
(ROOT / "indep_hilbert.json").write_text(json.dumps({"n": len(out), "all_match": all(r["match"] for r in out),
                                                      "rows": out}, indent=1))
print("n", len(out), "all_match", all(r["match"] for r in out))
