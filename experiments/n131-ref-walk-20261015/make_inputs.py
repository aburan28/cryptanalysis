#!/usr/bin/env python3
"""Freeze the public inputs (independent Python arithmetic, indep.py).

inputs/constants.json   curve orders, subgroup orders r, eigenvalues lambda,
                        signed-Frobenius group sizes, DP thresholds
inputs/n131_points.json 64 lane starts, 32 adding-walk jumps, stride, cursor:
                        public hash-to-curve points of ECC2K-130's order-r
                        subgroup (no log known), timing only
inputs/n83_points.json  the same at n = 83 (timing at the n = 83 unit)
inputs/panel64.json     the n = 83 64-point panel: crypto's
                        single_target_panel.public_point law, domain
                        kic-n83-single-target-public-point-v1, role eval,
                        seeds 0..63; seeds 0..15 must equal Panel B of
                        experiments/koblitz-single-target-n83-tier1-20261014
inputs/known_logs.json  4 targets [k]G with k published (positive control)

--check regenerates everything and compares byte for byte.
"""
import hashlib
import json
import sys
from math import comb, log2
from pathlib import Path

import indep

HERE = Path(__file__).resolve().parent
OUT = HERE / "inputs"
DOMAIN = "n131-ref-walk-20261015-v1"
PANEL_DOMAIN = "kic-n83-single-target-public-point-v1"
PANEL_B = HERE.parent / "koblitz-single-target-n83-tier1-20261014" / "inputs" / "targets.json"


def hx(v):
    return "0x%048x" % v


def dp_prob(n, parity, t):
    return sum(comb(n, w) for w in range(parity, t + 1, 2)) / 2 ** (n - 1)


def curve_record(n):
    c, order, h, r, roots = indep.setup(n)
    probe = indep.public_point(c, h, DOMAIN, "probe", 0, 17 if n == 131 else 11)
    lam = [l for l in roots if c.frob(probe) == c.mul(probe, l)]
    assert len(lam) == 1
    lam = lam[0]
    assert pow(lam, n, r) == 1 and lam != 1  # exact order n (n prime)
    # -1 is not a power of lambda (lambda has odd order), so A = 2n
    assert all(pow(lam, k, r) != r - 1 for k in range(n))
    return c, {"n": n, "a": c.a, "field_modulus": hx(c.f.m), "group_order": str(order), "cofactor": h,
               "r": str(r), "r_bits": r.bit_length(), "lambda": str(lam), "lambda_order": n,
               "signed_frobenius_A": 2 * n}, h, r, lam


def main():
    check = "--check" in sys.argv
    files = {}
    consts = {}
    curves = {}
    for n in (83, 131):
        c, rec, h, r, lam = curve_record(n)
        curves[n] = (c, h, r)
        parity = 1 if n == 83 else 0
        t = 31 if n == 83 else 52
        rec["hw_parity_of_subgroup_x"] = parity
        rec["dp_hw_threshold"] = t
        rec["dp_probability_log2"] = round(log2(dp_prob(n, parity, t)), 4)
        if n == 131:
            rec["dp_2009_hw_le_34_log2"] = round(log2(dp_prob(131, 0, 34)), 4)
        rec["floor_steps"] = "sqrt(pi r / (2 A))"
        consts[str(n)] = rec
    files["constants.json"] = consts

    for n, nb in ((131, 17), (83, 11)):
        c, h, r = curves[n]
        def pts(role, count):
            out = []
            for s in range(count):
                p = indep.public_point(c, h, DOMAIN, role, s, nb)
                assert c.on(p) and c.mul(p, r) is None
                assert bin(c.f.trace(p[0])).count("1") in (0, 1)
                out.append(p)
            return out
        starts, jumps, extra = pts("start", 64), pts("jump", 32), pts("stride_cursor", 2)
        tr = {c.f.trace(p[0]) for p in starts + jumps + extra}
        assert tr == {1 if n == 83 else 0}, tr
        files[f"n{n}_points.json"] = {
            "law": f"x = SHA-256('{DOMAIN}|<role>|<seed>|<counter>')[0:{nb}] little-endian mod 2^{n}, "
                   f"first counter whose x lifts; y by half-trace, sign bit 0 of digest byte {nb}; P = [h]P'. "
                   "No log is known.",
            "starts": [[hx(x), hx(y)] for x, y in starts],
            "jumps": [[hx(x), hx(y)] for x, y in jumps],
            "stride_cursor": [[hx(x), hx(y)] for x, y in extra],
        }

    c, h, r = curves[83]
    panel = []
    for s in range(64):
        x, y = indep.public_point(c, h, PANEL_DOMAIN, "eval", s, 8)
        panel.append({"id": s, "seed": s, "x": str(x), "y": str(y)})
    ref = json.loads(PANEL_B.read_text())["panel_b"]["points"]
    for e, p in zip(ref, panel[:16]):
        assert e["seed"] == p["seed"] and e["point"] == [p["x"], p["y"]], "panel law mismatch"
    files["panel64.json"] = {
        "law": "crypto single_target_panel.public_point, domain " + PANEL_DOMAIN + ", role eval, seeds 0..63; "
               "seeds 0..15 equal Panel B of koblitz-single-target-n83-tier1-20261014/inputs/targets.json "
               "(asserted). No scalar is known.",
        "targets": panel,
    }
    g = (6614244651398184860292015, 8868260410029249391539529)
    known = []
    for i in range(4):
        k = int.from_bytes(hashlib.sha256(f"{DOMAIN}|known|{i}".encode()).digest(), "little") % r
        x, y = c.mul(g, k)
        known.append({"id": 1000 + i, "x": str(x), "y": str(y), "known_d": str(k)})
    files["known_logs.json"] = {"law": "k = SHA-256('" + DOMAIN + "|known|<i>') little-endian mod r; Q = [k]G",
                                "targets": known}

    OUT.mkdir(exist_ok=True)
    bad = 0
    for name, val in files.items():
        text = json.dumps(val, indent=1, sort_keys=True) + "\n"
        path = OUT / name
        if check:
            if path.read_text() != text:
                print("MISMATCH", name)
                bad += 1
        else:
            path.write_text(text)
    if bad:
        sys.exit(1)
    print("inputs " + ("verified" if check else "written") + ": " + ", ".join(files))


if __name__ == "__main__":
    main()
