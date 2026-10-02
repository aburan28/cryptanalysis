"""Actual proof replay, counters, configuration and fresh context boundaries."""
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import unittest

from adapter import IdentityQuery,producer
from independent_checker import Checker,IDENTITY_MODES
from identity_accounting import reconcile_identity,per_record
from public_replay import Point
from test_symmetry import raw,words

HERE=Path(__file__).resolve().parent


class IdentityTests(unittest.TestCase):
    def test_complete_queries_replay_every_identity_coefficient(self):
        fixtures=json.loads(gzip.decompress((HERE.parent/'round40/fixtures/inputs.json.gz').read_bytes()))
        selected=[next(i for i in fixtures if i['nvars']==n and i['n']==31) for n in (18,21,24,27)]
        selected.append(next(i for i in fixtures if i['n']==83))
        audited=0
        for item in selected:
            shape=tuple(item[k] for k in ('n','mod','b','m','ell'))
            with IdentityQuery(*shape,identity_audit_test=True) as query:
                reference=None
                for transform in ('full','tile16'):
                    query.checker.configure_transform(transform)
                    for mode in IDENTITY_MODES:
                        query.checker.configure_identity(mode)
                        result=query.solve(Point(**item['target']))
                        self.assertTrue(result['verified'])
                        math=(result['proof_bytes'],result['basis_terms'],result['assignment'],result['basis_certificate']['solutions'])
                        if reference is None:reference=math
                        self.assertEqual(math,reference)
                        check=result['basis_certificate'];reconcile_identity(check,2*item['ell'],item['ell'],item['n'],audit=True)
                        audited+=check['identity_check_stats']['audit_coefficients']
        self.assertGreater(audited,0)

    def test_invalid_identities_audited_and_reused_scratch_refreshed(self):
        terms=[(4,1),(8,2),(12,4),(0,4)]
        packed=producer.Packed(4,3,terms)
        with producer.Producer(2,2,3) as p,Checker(2,2,3,identity_audit_test=True) as c:
            answer=p.produce(packed)
            self.assertGreater(len(answer['proof_bytes']),32)
            damaged=words(answer['proof_bytes']);damaged[5]^=1
            for symmetry in (False,True):
                c.configure_symmetry(symmetry)
                for mode in IDENTITY_MODES:
                    c.configure_identity(mode)
                    good=c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
                    self.assertTrue(good['verified']);reconcile_identity(good,2,2,3,audit=True)
                    bad=c.certify(packed,answer['roots'],answer['basis'],raw(damaged))
                    self.assertEqual(bad['code'],9)
                    self.assertGreater(bad['identity_check_stats']['audit_coefficients'],0)
                    again=c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
                    self.assertTrue(again['verified']);reconcile_identity(again,2,2,3,audit=True)

    def test_strict_configuration_lifecycle_and_concurrent_metadata(self):
        terms=[(4,1),(8,2),(12,4),(0,4)];packed=producer.Packed(4,3,terms)
        with producer.Producer(2,2,3) as p,Checker(2,2,3) as c:
            answer=p.produce(packed)
            for value in (None,True,0,[],{},'automatic','GROUPED'):
                with self.assertRaises(ValueError):c.configure_identity(value)
                with self.assertRaises(ValueError):Checker(2,2,3,identity=value)
            self.assertEqual(c.lib.check_identity_configure(c._handle,8),-1)
            for mode in IDENTITY_MODES:
                c.configure_identity(mode)
                def run(_):return c.certify(packed,answer['roots'],answer['basis'],answer['proof_bytes'])
                with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(run,range(16)))
                for row in rows:
                    reconcile_identity(row,2,2,3)
                    self.assertEqual(row['identity_check_stats'],rows[0]['identity_check_stats'])
                with self.assertRaises(ValueError):c.certify(packed,[],[[0]],answer['proof_bytes'][:-8])
                self.assertTrue(run(0)['verified'])
        with self.assertRaises(RuntimeError):c.configure_identity('dense')
        with self.assertRaises(RuntimeError):c.certify(packed,[],[[0]],answer['proof_bytes'])


if __name__=='__main__':unittest.main(verbosity=2)
