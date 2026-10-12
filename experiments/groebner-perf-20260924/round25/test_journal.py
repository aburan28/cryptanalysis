"""Recover all completed arms, reject corruption, retain truncated attempts."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from journal import Journal, recover, encode


class JournalTests(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'report.json.gz'
            r = {'schema':'synthetic-unit-test','status':'RUNNING','rows':[], 'candidates':{},
                 'admission':{'timed_attempts':0},'host':{},'source_snapshot':{'immutable':'x'*10000}}
            j = Journal(out)
            j.checkpoint(r)
            for i in range(8):
                row = {'workload_id':'test-only','repetition':i,'results':{}}
                r['rows'].append(row)
                j.checkpoint(r)
                r['candidates']['C'+str(i%2)] = {'policy':i%2}
                for arm in ('a','b','rho'):
                    row['results'][arm] = {'status':'synthetic'}
                    r['admission']['timed_attempts'] += 1
                    j.checkpoint(r)
                    saved, info = recover(j.path)
                    self.assertEqual(saved,r)
                    self.assertFalse(info['truncated_tail'])
            r.update(status='RECORDED',timing_admission_eligible=False)
            j.finish(r)
            self.assertEqual(json.loads(gzip.decompress(out.read_bytes())),r)
            self.assertEqual(recover(j.compressed)[0],r)
            self.assertFalse(j.path.exists())
            with self.assertRaises(RuntimeError): j.checkpoint(r)
            with self.assertRaises(FileExistsError): Journal(out)

    def test_partial_write_retains_prior_arms_and_checksum_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'report.json.gz'
            r = {'status':'RUNNING','rows':[], 'candidates':{},'host':{},'admission':{}}
            j = Journal(out)
            j.checkpoint(r)
            r['rows'].append({'workload_id':'test','repetition':0,'results':{'a':{'verified':True}}})
            j.checkpoint(r)
            j.close()
            original = j.path.read_bytes()
            with j.path.open('ab') as stream: stream.write(b'partial current arm')
            restored, info = recover(j.path)
            self.assertTrue(info['truncated_tail'])
            self.assertEqual(restored['status'],'INTERRUPTED')
            self.assertFalse(restored['timing_admission_eligible'])
            self.assertEqual(restored['rows'],r['rows'])
            j.path.write_bytes(original.replace(b'"verified":true',b'"verified":false'))
            with self.assertRaisesRegex(ValueError,'checksum'): recover(j.path)
            j.path.write_bytes(b'\n'.join(original.split(b'\n')[1:]))
            with self.assertRaisesRegex(ValueError,'chain'): recover(j.path)

    def test_checkpoint_work_grows_linearly(self):
        sizes = []
        for n in (16,32):
            with tempfile.TemporaryDirectory() as tmp:
                j = Journal(Path(tmp)/'r.gz')
                r = {'status':'RUNNING','rows':[], 'candidates':{},'host':{},'admission':{}}
                j.checkpoint(r)
                baseline_bytes = len(encode(r))
                for i in range(n):
                    r['rows'].append({'workload_id':'synthetic','repetition':i,'payload':'z'*10000})
                    j.checkpoint(r)
                    baseline_bytes += len(encode(r))
                sizes.append((j.bytes_written,baseline_bytes))
                j.close()
        self.assertLess(sizes[1][0]/sizes[0][0],2.1)
        self.assertGreater(sizes[1][1]/sizes[0][1],3.5)
        print('Synthetic checkpoint/reference serialized bytes:',sizes)

    def test_candidate_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = Journal(Path(tmp)/'r.gz')
            r = {'status':'RUNNING','rows':[], 'candidates':{'C':{'version':1}},'host':{},'admission':{}}
            j.checkpoint(r)
            r['candidates']['C']['version'] = 2
            with self.assertRaises(ValueError): j.checkpoint(r)
            j.close()

    def test_sync_failure_does_not_append_duplicate_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = Journal(Path(tmp)/'r.gz')
            r = {'status':'RUNNING','rows':[], 'candidates':{},'host':{},'admission':{}}
            j.checkpoint(r)
            r['rows'].append({'workload_id':'synthetic','repetition':0,'results':{'a':'retained'}})
            with patch('journal.os.fsync',side_effect=OSError('injected sync failure')):
                with self.assertRaises(OSError): j.checkpoint(r)
            with self.assertRaises(RuntimeError): j.checkpoint(r)
            restored, _ = recover(j.path)
            self.assertEqual(restored['rows'],r['rows'])
            self.assertEqual(restored['status'],'RUNNING')


if __name__ == '__main__': unittest.main()
