"""Cross-boundary lifetime, fresh-input, and fail-closed correctness controls."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
import common
from common import Context
from query import Query,ARMS,abi

class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts=[Context(sanitizer=s) for s in (False,True)]

    def test_leased_transport_without_repacking(self):
        for ctx in self.contexts:
            for arm,q in ctx.queries.items():
                work=q.workspace(2,2,[1,2,0]);addresses=work.buffer_addresses
                for coefficients in ({1:1,2:2},{1:1,2:2,0:3},{1:1,2:2}):
                    with work.borrow_mapping(coefficients) as packed:
                        with patch.object(abi,'InputOwner',side_effect=AssertionError('repacked input')):
                            result=q.compute(packed,export_proof=True)
                        self.assertTrue(result['verified'],(arm,result))
                        self.assertEqual(work.buffer_addresses,addresses)
                        expected=0 if 0 not in coefficients else 3
                        self.assertTrue(all(sum((m&expected)==m for m in row)%2==0 for row in result['basis']))
                    with self.assertRaises(RuntimeError):q.compute(packed)

    def test_cross_thread_and_nested_lease_rejected(self):
        q=self.contexts[0].queries['release-live'];work=q.workspace(1,1,[1])
        with work.borrow_mapping({1:1}) as packed:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future=executor.submit(q.compute,packed)
                with self.assertRaises(RuntimeError):future.result()
            with self.assertRaises(RuntimeError):
                with work.borrow_mapping({1:1}):pass
        with self.assertRaises(ValueError):q.compute({1:1})

    def test_changed_targets_reuse_only_buffers(self):
        for ctx in self.contexts:
            for arm in ARMS:
                outputs=[]
                self.assertNotEqual(ctx.cases['pdp-6-seed-1']['target_x'],ctx.cases['pdp-6-seed-3']['target_x'])
                for name in ('pdp-6-seed-1','pdp-6-seed-3','pdp-6-seed-1'):
                    result=ctx.run(name,arm)['result']
                    self.assertTrue(result['verified'],result)
                    self.assertTrue(result['reference_equations_and_curve_replay'])
                    outputs.append((result['basis'],result['proof'],result['assignment']))
                self.assertEqual(outputs[0],outputs[2]);self.assertNotEqual(outputs[0],outputs[1])

    def test_exhaustion_does_not_escape_as_success(self):
        for ctx in self.contexts:
            for arm in ARMS:
                for limits in ({'max_work':0},{'max_check_work':0},{'max_terms':0}):
                    result=ctx.run('pdp-6-seed-1',arm,limits=limits)['result']
                    self.assertFalse(result['verified']);self.assertNotIn('assignment',result)
                    self.assertNotIn('basis',result)

    def test_curve_failure_not_promoted(self):
        ctx=self.contexts[0]
        with patch.object(common,'verify_solution',return_value=False):
            result=ctx.run('pdp-6-seed-1','release-live')['result']
        self.assertTrue(result['algebra_verified']);self.assertFalse(result['verified'])
        self.assertEqual(result['status'],'gb-no-verified-solution');self.assertNotIn('assignment',result)

    def test_final_reference_failure_not_promoted(self):
        ctx=self.contexts[0];original=ctx.instances['pdp-6-seed-1'];check=common.verify_solution
        def only_packed(instance,assignment):
            return False if instance is original else check(instance,assignment)
        with patch.object(common,'verify_solution',side_effect=only_packed):
            result=ctx.run('pdp-6-seed-1','completion')['result']
        self.assertFalse(result['verified']);self.assertEqual(result['status'],'reference-replay-failed')
        self.assertNotIn('reference_equations_and_curve_replay',result)

    def test_corrupted_frozen_descent_rejected(self):
        ctx=self.contexts[0];name='pdp-6-seed-1';saved=ctx.anfs[name]
        ctx.anfs[name]={**saved,0:saved.get(0,0)^1}
        try:
            with self.assertRaisesRegex(ValueError,'fresh packed coefficients'):ctx.run(name,'legacy')
        finally:ctx.anfs[name]=saved

if __name__=='__main__':unittest.main()
