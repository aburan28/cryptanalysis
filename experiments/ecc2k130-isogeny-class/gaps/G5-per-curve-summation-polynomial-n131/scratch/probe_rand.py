import sys, json, random, time; sys.path.insert(0,'.')
import g5lib as L
CTRL=json.load(open('../controls.json'))
C=L.CurveCtx('E0', L.dec(1), order=L.ecc2k.CARD)
for k in (5,6):
    basis=[L.dec(u) for u in CTRL['random_bases'][0][:k]]
    R=C.random_odd_target(random.Random(L.seed_int("G5","E0","rand",0)))
    anf=L.descended_anf(3,basis,C.b,R[0]); nv=3*k
    gens,nd=L.build_generators(anf,nv)
    t=time.process_time(); fr=L.formal_regularity(gens,nv,300); print(k,'formal',fr.get('status'),fr.get('d_reg'),fr.get('top_quotient_dim'),fr.get('generator_top_degree_hist'),round(time.process_time()-t,1),flush=True)
    ms,gb=L.run_msolve(gens,nv,300,'probe%d'%k); print(k,'msolve',ms.get('status'),ms.get('max_degree'),ms.get('degree_sequence'),ms.get('msolve_cpu_reported'),round(ms['cpu'],1),ms.get('max_matrix'),flush=True)
