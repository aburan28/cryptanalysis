#!/usr/bin/env python3
"""Independent check (indep.py arithmetic, no shared code) of the Rust walk's
group law, scalar multiplication, Frobenius, canonical forms, one Bailey step
(`emit` output), the f131.h point KAT, and every n = 83 solve row's
logarithm.

  check_points.py <emit.json> <point_kat.txt> <out.json> [solves.jsonl ...]
"""
import json
import sys

import indep

FIELDS = {}


def pt(v):
    return None if v is None else (int(v[0], 16), int(v[1], 16))


def check_emit(rows, n):
    c, order, h, r, roots = indep.setup(n)
    lam = [l for l in roots if c.frob(pt(rows[0]["P"])) == c.mul(pt(rows[0]["P"]), l)][0]
    bad = []
    for i, e in enumerate(rows):
        P, Q = pt(e["P"]), pt(e["Q"])
        k = int(e["k"], 16)
        orbit = set()
        for t in range(n):
            f = c.frob(P, t)
            orbit.add(f)
            orbit.add(c.neg(f))
        tests = {
            "on_curve": c.on(P) and c.on(Q),
            "subgroup": c.mul(P, r) is None,
            "sum": c.add(P, Q) == pt(e["sum"]),
            "dbl": c.add(P, P) == pt(e["dbl"]),
            "neg": c.neg(P) == pt(e["neg"]) and c.add(P, pt(e["neg"])) is None,
            "kP": c.mul(P, k) == pt(e["kP"]),
            "frob": c.frob(P, e["t"]) == pt(e["frobP"]) == c.mul(P, pow(lam, e["t"], r)),
            "canon_in_orbit": pt(e["canon"]) in orbit,
            "canon_k": (c.neg(c.frob(P, e["canon_k"])) if e["canon_neg"] else c.frob(P, e["canon_k"])) == pt(e["canon"]),
            "bailey_next": c.add(P, c.frob(P, e["bailey_j"])) == pt(e["bailey_next"])
                           == c.mul(P, (1 + pow(lam, e["bailey_j"], r)) % r),
            "hw_parity_is_trace": e["hw"] % 2 == c.f.trace(P[0]),
        }
        bad += [f"n{n} row {i} {k}" for k, ok in tests.items() if not ok]
    return len(rows), bad


def check_kat(path):
    f = indep.Field(131, indep.M131)
    c = indep.Curve(f, 0)
    bad = []
    lines = open(path).read().split("\n")
    lines = [l for l in lines if l]
    for i, l in enumerate(lines):
        v = [int(h, 16) for h in l.split()]
        w = [v[j] | v[j + 1] << 64 | v[j + 2] << 128 for j in range(0, 39, 3)]
        a, ia, sk, _, _, x1, y1, x2, y2, x3, y3, x4, y4 = w
        if f.mul(a, ia) != 1:
            bad.append(f"kat {i} inv")
        s = a
        for _ in range(i % 131):
            s = f.sqr(s)
        if s != sk:
            bad.append(f"kat {i} sigma")
        lam = f.mul(y1 ^ y2, f.inv(x1 ^ x2))
        if (f.sqr(lam) ^ lam ^ x1 ^ x2, f.mul(lam, x1 ^ (f.sqr(lam) ^ lam ^ x1 ^ x2)) ^ (f.sqr(lam) ^ lam ^ x1 ^ x2) ^ y1) != (x3, y3):
            bad.append(f"kat {i} add")
        l2 = x1 ^ f.mul(y1, f.inv(x1))
        X = f.sqr(l2) ^ l2
        if (X, f.sqr(x1) ^ f.mul(l2 ^ 1, X)) != (x4, y4):
            bad.append(f"kat {i} double")
    return len(lines), bad


def check_solves(paths):
    c, order, h, r, roots = indep.setup(83)
    g = (6614244651398184860292015, 8868260410029249391539529)
    rows, bad, unverified = 0, [], 0
    for p in paths:
        for line in open(p):
            e = json.loads(line)
            rows += 1
            if e["d"] is None or not e["verified"]:
                unverified += 1
                continue
            q = None
            # the target point is recomputed from the row's own inputs file id
            tgt = TARGETS[e["target"]]
            if c.mul(g, int(e["d"])) != tgt:
                bad.append(f"solve {e['arm']} target {e['target']} seed {e['seed']}")
            if e["known_match"] is False:
                bad.append(f"known log mismatch {e['target']}")
    return rows, unverified, bad


TARGETS = {}


def main():
    emit = json.load(open(sys.argv[1]))
    out = {}
    allbad = []
    for n in (131, 83):
        cnt, bad = check_emit(emit[f"n{n}"], n)
        out[f"emit_n{n}_rows"] = cnt
        allbad += bad
    cnt, bad = check_kat(sys.argv[2])
    out["point_kat_lines"] = cnt
    allbad += bad
    if len(sys.argv) > 4:
        for f in ("inputs/panel64.json", "inputs/known_logs.json"):
            for t in json.load(open(f))["targets"]:
                TARGETS[t["id"]] = (int(t["x"]), int(t["y"]))
        rows, unver, bad = check_solves(sys.argv[4:])
        out["solve_rows"] = rows
        out["solve_rows_unverified"] = unver
        allbad += bad
    out["failures"] = allbad
    out["pass"] = not allbad
    json.dump(out, open(sys.argv[3], "w"), indent=1)
    print(json.dumps(out))
    sys.exit(0 if not allbad else 1)


if __name__ == "__main__":
    main()
