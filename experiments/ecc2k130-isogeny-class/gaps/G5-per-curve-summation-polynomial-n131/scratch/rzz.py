import sys, json, random; sys.path.insert(0,'.')
import g5lib as L
C=json.load(open('../controls.json'))
c=[x for x in C['curves'] if x['label']=='RZz'][0]
CC=L.CurveCtx('RZz', L.dec(c['b_int']), order=int(c['order']))
print('two', CC.two, 'nodd', CC.nodd % 2)
for k in (4,5,6):
    dom=L.factor_domain(CC, L.poly_basis(k))
    img=L.enumerate_image(dom,3)
    print(k, len(dom['lifts']), len(img), len(dom['tadd']))
    R=CC.random_odd_target(random.Random(1)); print((CC.nodd*R).is_zero())
    print(L.planted_target(CC, dom, 3, random.Random(2), odd_only=False)[1]); print(len(L.enumerate_image(dom,3,odd_only=False)))
