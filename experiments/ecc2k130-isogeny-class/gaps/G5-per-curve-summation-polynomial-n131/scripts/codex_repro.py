"""Q1: reproduce Codex run-03's k = 6 row-reduced formal d_reg cells exactly.

Codex (run-03 selected_scaling.py) picks target_key = sorted(image)[sha256("{id}:{k}:run03") mod
len(image)], builds make_equations (S4 bits + membership ANF x3 + distinctness x3 + field eqs),
row-reduces, and reports d_reg of the top-form ideal.  Recorded values (Codex raw rows
run-03-scaling/<id>.jsonl, k = 6):  E0 8/623 (139 reduced eqs), A010 11/8035, A112 11/8036,
A127 11/8349, B000 10/7900, B095 10/7901 (155 reduced eqs each).
Usage: sage -python codex_repro.py LABEL [LABEL ...]   -> raw/codex_repro_<label>.json
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g5lib as L  # noqa: E402

CODEX = {  # from Codex run-03 raw rows (read-only copies listed in results.json)
    "E0": ("2562223607185829189002080094476514195703", 8, 623, 155, 139),
    "A010": ("1830938390556306420088578533990920343964", 11, 8035, 155, 155),
    "A112": ("1573115913423154465151863051549845582212", 11, 8036, 155, 155),
    "A127": ("1122983159519261315642474751484366827515", 11, 8349, 155, 155),
    "B000": ("108805040796381756273554323987058579168", 10, 7900, 155, 155),
    "B095": ("1964473839030867872366712841096239290974", 10, 7901, 155, 155),
}

k, m = 6, 3
for lab in sys.argv[1:]:
    rec = L.ecc2k.RECORDS[lab]
    C = L.CurveCtx(lab, L.dec(rec["b_int"]), order=L.ecc2k.CARD)
    basis = L.poly_basis(k)
    t0 = time.time()
    dom = L.factor_domain(C, basis)
    img = L.enumerate_image(dom, m)
    t_img = time.time() - t0
    seed = int.from_bytes(hashlib.sha256(f"{lab}:{k}:run03".encode()).digest(), "big")
    key = sorted(img)[seed % len(img)]
    tx, dreg_c, dim_c, raw_c, red_c = CODEX[lab]
    out = {"label": lab, "k": k, "m": m, "x_count": len(dom["lifts"]), "image_size": len(img),
           "image_seconds": t_img, "target_x_selected": str(key[0]),
           "target_matches_codex": str(key[0]) == tx}
    r = L.dec(key[0])
    anf = L.descended_anf(m, basis, C.b, r)
    nv = m * k
    gens, nd = L.build_generators(anf, nv, k, m, "codex", set(dom["lifts"]))
    red = L.row_reduce(gens, nv)
    out.update({"raw_equations": len(gens), "reduced_equations": len(red),
                "descended_equations": nd, "descended_rank": L.coeff_rank(anf)})
    fr = L.formal_regularity(gens, nv, cap=1200)
    out["formal"] = fr
    out["codex_recorded"] = {"d_reg": dreg_c, "top_quotient_dim": dim_c, "raw_equations": raw_c,
                             "reduced_equations": red_c}
    out["reproduced"] = (out["target_matches_codex"] and fr.get("d_reg") == dreg_c
                         and fr.get("top_quotient_dim") == dim_c and len(gens) == raw_c
                         and len(red) == red_c)
    # exact solution set of the Codex system (planted/image target: expect 6 * #witness triples)
    sols = L.solutions_bruteforce(anf, nv)
    allowed = set(dom["lifts"])
    kmask = (1 << k) - 1
    sols_c = [a for a in sols if all(((a >> (i * k)) & kmask) in allowed for i in range(m))
              and len({(a >> (i * k)) & kmask for i in range(m)}) == m]
    out["plain_solutions"] = len(sols)
    out["codex_solutions"] = len(sols_c)
    out["expected_codex_solutions"] = 6 * len(img[key])
    ms, gb = L.run_msolve(gens, nv, 600, f"codexrepro{lab}")
    if gb is not None:
        cnt, ok = L.gb_solution_count(gb, nv, sols_c)
        ms["solution_count"] = cnt
        ms["gb_vanishes_on_bruteforce_solutions"] = ok
    ms.pop("rounds", None)
    out["msolve_codex_system"] = ms
    print(json.dumps({x: out[x] for x in out if x != "formal"}), flush=True)
    print(json.dumps(fr), flush=True)
    (HERE.parent / "raw" / f"codex_repro_{lab}.json").write_text(json.dumps(out, indent=1))
