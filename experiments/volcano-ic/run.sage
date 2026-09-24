# Driver for the n=19 volcano index-calculus study.
#
#   sage run.sage census <shard> <shards>          all 457 curves, tier A
#   sage run.sage ecdlp  <shard> <shards> <ids>    full IC, 10 instances, tier B
#
# Tier A per curve: factor base, four-torsion tags, exact relation yield by
# enumerating every factor-base pair, formal dreg on sampled targets, and a
# sample of Groebner decompositions drawn from each ECDLP instance.
# Tier B per curve and instance: complete index calculus, verified log.

import os
import random

HERE = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv[0] else '.'
load(os.path.join(HERE, 'ic.sage'))

N_BITS, K = 19, 10
MODULUS = list(reversed([1, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1]))
ORDER, COFACTOR = 523492, 4
SCALARS_SEED = 20260924
N_INSTANCES = 10
CENSUS_TARGETS_PER_INSTANCE = 10
DREG_TARGETS = 3


def loadCurves(fld):
    """E0 plus the 456 floor descendants, labelled by Frobenius orbit.

    Squaring b maps E_b to its Frobenius conjugate E_{b^2}; the 456
    descendants split into 24 orbits of 19. Orbit labels are ordered by the
    smallest integer encoding in the orbit; the index inside an orbit is the
    power of Frobenius applied to that smallest element."""
    text = open(os.path.join(HERE, 'data', 'isoclass19.txt')).read()
    z = fld.z
    entries = sage_eval(text.replace('\n', ''), locals={'z': z})
    enc = lambda e: ZZ(e.polynomial().change_ring(ZZ)(2))
    bs = [fld.F(e[0]) for e in entries]
    assert all(e[1] == 0 for e in entries) and len(bs) == 457
    one = fld.F(1)
    assert one in bs
    rest = set(bs) - {one}
    orbits = []
    while rest:
        b0 = min(rest, key=enc)
        orb = [b0 ** (2 ** j) for j in range(N_BITS)]
        assert len(set(orb)) == N_BITS and set(orb) <= rest
        rest -= set(orb)
        orbits.append(orb)
    orbits.sort(key=lambda o: enc(o[0]))
    curves = [('E0', one, None, None)]
    for oi, orb in enumerate(orbits):
        for j, b in enumerate(orb):
            curves.append(('O%02d.%02d' % (oi, j), b, oi, j))
    return curves


def scalars():
    rng = random.Random(int(SCALARS_SEED))
    p = ORDER // COFACTOR
    return [int(rng.randrange(2, int(p) - 1)) for _ in range(N_INSTANCES)]


def generator(cur, cid):
    # Deterministic subgroup generator: cofactor times a seeded random point.
    rng = random.Random('gen:' + cid)
    while True:
        x = cur.fld.F.from_integer(rng.randrange(1, 2 ** N_BITS))
        pts = cur.E.lift_x(x, all=True)
        if pts:
            P = cur.h * pts[0]
            if not P.is_zero():
                return P


def tags(cur):
    """Z/4 component of each factor-base point: E(F) = Z/4 x Z/p here."""
    p = cur.p
    T = None
    rng = random.Random('tags')
    while T is None:
        x = cur.fld.F.from_integer(rng.randrange(1, 2 ** N_BITS))
        pts = cur.E.lift_x(x, all=True)
        if pts:
            c = p * pts[0]
            if c.order() == 4:
                T = c
    table = {cur.E(0): 0, T: 1, 2 * T: 2, 3 * T: 3}
    return {x: table[p * P] for x, P in cur.fb.items()}


def exactYield(cur, tg):
    """Distinct prime-subgroup targets (up to sign) reachable as +-P1 +- P2."""
    xs = cur.xs
    seen = set()
    eligible = 0
    for i in range(len(xs)):
        P1, t1 = cur.fb[xs[i]], tg[xs[i]]
        for j in range(i, len(xs)):
            P2, t2 = cur.fb[xs[j]], tg[xs[j]]
            if (t1 + t2) % 4 == 0:
                R = P1 + P2
                if not R.is_zero():
                    eligible += 1
                    seen.add(R[0])
            if i != j and (t1 - t2) % 4 == 0:
                R = P1 - P2
                if not R.is_zero():
                    eligible += 1
                    seen.add(R[0])
    # x-coordinate identifies +-R; the subgroup has (p-1)/2 such classes.
    return eligible, len(seen), len(seen) / ((cur.p - 1) / 2)


def plain(o):
    # Sage Integer / RealNumber leak into records from preparsed literals.
    try:
        return int(o) if o == int(o) and not isinstance(o, float) else float(o)
    except (TypeError, ValueError):
        return str(o)


def done(path):
    out = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                r = json.loads(line)
                out.add((r['curve'], r.get('instance')))
            except ValueError:
                pass
    return out


def census(shard, shards):
    fld = Field(N_BITS, MODULUS, K)
    curves = loadCurves(fld)
    path = os.path.join(HERE, 'results', 'census-%d.jsonl' % shard)
    skip = done(path)
    ss = scalars()
    with open(path, 'a') as out:
        for idx, (cid, b, orbit, power) in enumerate(curves):
            if idx % shards != shard or (cid, None) in skip:
                continue
            t0 = time.perf_counter()
            cur = Curve(fld, 0, b, ORDER, COFACTOR)
            tg = tags(cur)
            counts = [sum(1 for v in tg.values() if v == t) for t in range(4)]
            t1 = time.perf_counter()
            eligible, distinct, prob = exactYield(cur, tg)
            t2 = time.perf_counter()
            P = generator(cur, cid)
            rng = random.Random('census:' + cid)
            dregs = []
            for _ in range(DREG_TARGETS):
                R = rng.randrange(1, int(cur.p)) * P
                dregs.append(int(topDegreeDreg(fld, [f for f in fld.system(R[0], b) if f != 0])))
            t3 = time.perf_counter()
            per = []
            for ii, s in enumerate(ss):
                Q = s * P
                st = {'build_s': 0.0, 'gb_s': 0.0, 'gb_calls': 0, 'nonempty': 0, 'spurious': 0}
                hits = 0
                for _ in range(CENSUS_TARGETS_PER_INSTANCE):
                    R = rng.randrange(1, int(cur.p)) * P + rng.randrange(1, int(cur.p)) * Q
                    if solveRelation(cur, R, st) is not None:
                        hits += 1
                st['relations'] = hits
                per.append(st)
            t4 = time.perf_counter()
            rec = {'curve': cid, 'orbit': orbit, 'frob_power': power, 'b': str(b),
                   'fb_size': len(cur.xs), 'tag_counts': counts,
                   'eligible_signed_pairs': eligible, 'distinct_targets': distinct,
                   'exact_decomp_prob': float(prob),
                   'expected_attempts_per_dlp': float((len(cur.xs) + 10) / prob),
                   'dreg_samples': dregs, 'gb_sample': per,
                   'seconds': {'setup': t1 - t0, 'yield': t2 - t1, 'dreg': t3 - t2, 'gb_sample': t4 - t3}}
            out.write(json.dumps(rec, default=plain) + '\n')
            out.flush()
            print(cid, len(cur.xs), '%.4f' % prob, dregs, '%.1fs' % (t4 - t0), flush=True)


def ecdlp(shard, shards, ids):
    fld = Field(N_BITS, MODULUS, K)
    curves = {c[0]: c for c in loadCurves(fld)}
    path = os.path.join(HERE, 'results', 'ecdlp-%d.jsonl' % shard)
    skip = done(path)
    ss = scalars()
    jobs = [(cid, ii) for cid in ids for ii in range(len(ss))]
    with open(path, 'a') as out:
        for jn, (cid, ii) in enumerate(jobs):
            if jn % shards != shard or (cid, ii) in skip:
                continue
            _, b, orbit, power = curves[cid]
            cur = Curve(fld, 0, b, ORDER, COFACTOR)
            P = generator(cur, cid)
            Q = ss[ii] * P
            rng = random.Random('ecdlp:%s:%d' % (cid, ii))
            st = solveDlp(cur, P, Q, rng)
            st.update({'curve': cid, 'orbit': orbit, 'frob_power': power, 'instance': ii,
                       'scalar': int(ss[ii]), 'correct': st['log'] == ss[ii] % cur.p})
            out.write(json.dumps(st, default=plain) + '\n')
            out.flush()
            print(cid, ii, st['recovered'], st['attempts'], '%.1fs' % st['total_s'], flush=True)


if __name__ == '__main__' and len(sys.argv) > 1:
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    mode = sys.argv[1]
    if mode == 'census':
        census(int(sys.argv[2]), int(sys.argv[3]))
    elif mode == 'ecdlp':
        ecdlp(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4].split(','))
