"""Cross-check native/libf83.dylib against Sage: field ops, lifts, signs, Z/4 tags,
3-summand images (counts and target sets) and 4-summand images on four curves.

    sage -python check_f83lib.py
"""
import sys, json, random, time, itertools
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import m83, f83lib, run01_comparison as r1
rng = random.Random(1)
F = m83.FIELD
for _ in range(200):
    a, b = rng.getrandbits(83), rng.getrandbits(83)
    assert f83lib.mul(a, b) == m83.enc(m83.dec(a) * m83.dec(b))
    if a: assert f83lib.inv(a) == m83.enc(1 / m83.dec(a))
    assert f83lib.trace(a) == int(m83.dec(a).trace())
inv = m83.load_inventory()
byid = {c['curve_id']: c for c in inv}
for cid in ['E0', 'O00-00', 'O41-17', 'O77-82']:
    c = byid[cid]
    E = m83.curve(c['b'])
    for k, prof in [(4, 'polynomial'), (4, 'random'), (5, 'polynomial')]:
        dom = r1.factor_domain(E, k, prof)
        img = r1.enumerate_image(dom)
        basis = [m83.enc(u) for u in dom['basis']]
        tt = f83lib.ratx(int(c['b']), basis)
        masks = [m for m in range(1 << k) if tt[m]]
        assert masks == sorted(dom['lifts']), (cid, k, prof)
        xs = [m83.enc(dom['values'][m]) for m in masks]
        ys, tags = f83lib.points(int(c['b']), xs)
        for m, y, t in zip(masks, ys, tags):
            assert m83.enc(dom['lifts'][m][0][1]) == y
            assert dom['tags'][m][0] == t, (cid, m, dom['tags'][m], t)
        st = f83lib.image(int(c['b']), xs, ys, tags, 3, targets_cap=100000)
        assert st['eligible_signed_tuples'] == img['eligible_signed_triples']
        assert st['prime_subgroup_distinct_targets'] == len(img['image'])
        assert st['full_distinct_targets'] == img['full_distinct_targets']
        assert set(st['targets']) == set(img['image'].keys())
        # 4-summand exact check vs Sage on k=4 only (small)
        if k == 4:
            pts = {m: dom['lifts'][m] for m in masks}
            cnt = 0; tg = set()
            for quad in itertools.combinations(masks, 4):
                for sg in itertools.product(range(2), repeat=4):
                    if sum(dom['tags'][m][s] for m, s in zip(quad, sg)) % 4 == 0:
                        cnt += 1
                        S = sum((pts[m][s] for m, s in zip(quad, sg)), E(0))
                        if not S.is_zero(): tg.add(m83.point_key(S))
            st4 = f83lib.image(int(c['b']), xs, ys, tags, 4)
            assert st4['eligible_signed_tuples'] == cnt and st4['prime_subgroup_distinct_targets'] == len(tg)
        print(cid, k, prof, len(masks), st['eligible_signed_tuples'], st['prime_subgroup_distinct_targets'], 'ok')
t0 = time.time()
c = byid['O00-00']
basis = [m83.enc(m83.W ** i) for i in range(20)]
tt = f83lib.ratx(int(c['b']), basis)
print('ratx 2^20 seconds', round(time.time() - t0, 3), int(tt.sum()))
