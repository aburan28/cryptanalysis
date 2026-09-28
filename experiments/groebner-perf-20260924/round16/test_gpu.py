"""Independent GPU roots versus CPU/Python certificates, including failures."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as ct
from dataclasses import replace
from itertools import product
import random
import unittest

from gpu_query import query, NativeDescent, GPUStats, HERE
from boolean_certificate_native import Certificate, _pack
from boolean_basis import certify_boolean_basis
from descend import make_instance


def semantics(certificate):
    return {k:v for k,v in certificate.items() if k not in ('backend','evaluation_counts','gpu_timing')}


class GPUTests(unittest.TestCase):
    def test_native_abi_rejections_do_not_dispatch(self):
        u32,u64=ct.c_uint32,ct.c_uint64
        for sanitized,arm in product((False,True),('gpu','gpu-spin')):
            with query(2,1,arm,sanitizer=sanitized) as gpu:
                verifier=gpu._verifier;lib=verifier.lib
                masks=(u32*1)(1);coefficients=(u64*1)(1)
                basis,offsets=_pack([[1]],2)
                args=[verifier.handle,2,1,masks,coefficients,1,basis,1,offsets,1]
                for change in ({0:None},{1:3},{2:2},{3:None},{4:None},{6:None},{8:None},
                               {3:(u32*1)(4)},{4:(u64*1)(2)},
                               {8:(u32*2)(1,1)},{8:(u32*2)(0,0)},
                               {6:(u32*1)(4)}):
                    values=args[:]
                    for index,value in change.items(): values[index]=value
                    certificate=Certificate();stats=GPUStats();stats.calls=99
                    code=lib.gpu_certificate_compute(*values,ct.byref(certificate),ct.byref(stats))
                    self.assertEqual((code,certificate.code,stats.calls),(6,6,0))
                for n,e,spin in ((0,1,0),(21,1,0),(2,0,0),(2,4097,0),(2,1,5001),(20,4096,0)):
                    self.assertFalse(lib.gpu_certificate_create(n,e,str(HERE/'direct_truth.metal').encode(),spin))
                self.assertEqual(lib.gpu_certificate_device_name(None),b'')
                certificate=Certificate();stats=GPUStats()
                self.assertEqual(lib.gpu_certificate_compute(*args,None,ct.byref(stats)),6)
                self.assertEqual(lib.gpu_certificate_compute(*args,ct.byref(certificate),None),6)
                self.assertTrue(gpu.certify({1:1},[[1]])['verified'])

    def test_random_truth_sets_and_mutations(self):
        rng=random.Random(2026092604);comparisons=0
        for n,e in ((1,1),(3,31),(6,63),(6,64),(7,65),(8,128),(8,4096)):
            with query(n,e,'ordered') as cpu:
                for sanitized,arm in product((False,True),('gpu','gpu-spin')):
                    with query(n,e,arm,sanitizer=sanitized) as gpu:
                        for repeat in range(6):
                            anf={rng.randrange(1<<n):rng.getrandbits(e) for _ in range(2+repeat*4)}
                            if repeat%2==0:
                                planted=rng.randrange(1<<n);value=0
                                for m,c in anf.items():
                                    if m&~planted==0: value^=c
                                anf[0]=anf.get(0,0)^value
                            original=cpu.compute(anf);result=gpu.compute(anf)
                            self.assertTrue(original['groebner_verified'],original)
                            self.assertTrue(result['groebner_verified'],result)
                            self.assertEqual(original['basis_terms'],result['basis_terms'])
                            self.assertEqual(semantics(original['basis_certificate']),semantics(result['basis_certificate']))
                            equations=[[m for m,c in anf.items() if c>>j&1] for j in range(e)]
                            self.assertTrue(certify_boolean_basis(n,equations,result['basis_terms'])['verified'])
                            basis=original['basis_terms']
                            if basis:
                                bad=[r[:] for r in basis];bad[0]+=bad[0][:1]
                                self.assertEqual(semantics(cpu.certify(anf,bad)),semantics(gpu.certify(anf,bad)))
                            comparisons+=1
        print('GPU/CPU/Python random certificate comparisons:',comparisons)

    def test_zero_full_domain_duplicates_and_raw_rejections(self):
        for sanitized,arm in product((False,True),('gpu','gpu-spin')):
            with query(20,1,'ordered') as cpu,query(20,1,arm,sanitizer=sanitized) as gpu:
                self.assertEqual(semantics(cpu.certify({},[])),semantics(gpu.certify({},[])))
                self.assertEqual(gpu.certify({},[])['root_count'],1<<20)
            with query(2,1,'ordered') as cpu,query(2,1,arm,sanitizer=sanitized) as gpu:
                masks=(ct.c_uint32*4)(1,0,1,1);coefficients=(ct.c_uint64*4)(1,0,1,1)
                self.assertEqual(semantics(cpu._certify(masks,coefficients,[[1]])),
                                 semantics(gpu._certify(masks,coefficients,[[1]])))
                for invalid in ({4:1},{0:2}):
                    with self.assertRaises(ValueError): gpu.certify(invalid,[[1]])
                for basis in ([[]],[[1,1]],[[1,0]],[],[[1],[1]]):
                    self.assertEqual(semantics(cpu.certify({1:1},basis)),semantics(gpu.certify({1:1},basis)))
                self.assertTrue(gpu.certify({1:1},[[1]])['verified'])
            with query(2,2,arm,sanitizer=sanitized) as gpu,query(2,2,'ordered') as cpu:
                self.assertEqual(semantics(cpu.certify({1:1,2:2},[[1,2],[2]])),
                                 semantics(gpu.certify({1:1,2:2},[[1,2],[2]])))
        for n,e in ((0,1),(21,1),(2,0),(2,4097),(20,4096)):
            with self.assertRaises(ValueError): query(n,e)

    def test_concurrent_freshness_and_closed_lifetime(self):
        for arm in ('gpu','gpu-spin'):
            with query(6,1,arm) as gpu:
                calls=[({1:1},[[1]],True),({1:1,0:1},[[1]],False),({},[],True)]*12
                with ThreadPoolExecutor(max_workers=4) as executor:
                    results=list(executor.map(lambda p:gpu.certify(p[0],p[1]),calls))
                self.assertEqual([r['verified'] for r in results],[p[2] for p in calls])
                self.assertEqual([r['root_count'] for r in results],[32,32,64]*12)
            with self.assertRaises(RuntimeError): gpu.certify({},[])
            gpu.close()

    def test_complete_queries_retain_equations_and_curve_replay(self):
        for (n,ell,seed),arm in product(((11,2,1),(31,6,101),(83,2,2)),('gpu','gpu-spin')):
            original=make_instance(n,3,ell,seed=seed)
            with NativeDescent(n,original.mod,original.b,3,ell) as native, \
                    query(original.nvars,n,'ordered') as cpu,query(original.nvars,n,arm) as gpu:
                anf=native.descend_packed(original.xR)
                a=cpu.solve(replace(original,anf=anf));b=gpu.solve(replace(original,anf=anf))
                self.assertTrue(a.get('verified'),a);self.assertTrue(b.get('verified'),b)
                self.assertEqual((a['basis_sha256'],a['assignment']),(b['basis_sha256'],b['assignment']))
                self.assertEqual(semantics(a['basis_certificate']),semantics(b['basis_certificate']))
                self.assertEqual(original.evaluate(b['assignment']),0)


if __name__=='__main__': unittest.main()
