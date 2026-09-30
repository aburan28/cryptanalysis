"""Interrupted evidence retains exactly the proofs already checkpointed."""
import copy
from pathlib import Path
import tempfile
import unittest

from certificate_journal import Journal, recover


class JournalTests(unittest.TestCase):
    def test_incremental_proofs_and_truncated_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'report.json.gz'
            report = {'status':'RUNNING', 'rows':[], 'candidates':{}, 'proofs':{}}
            journal = Journal(output)
            journal.checkpoint(report)
            report['proofs']['first'] = {'bytes':8, 'base64':'AAAAAAAAAAA=', 'byteorder':'little'}
            report['rows'].append({'workload_id':'fixture', 'repetition':0})
            journal.checkpoint(report)
            journal.close()
            with journal.path.open('ab') as stream:
                stream.write(b'partial record')
            restored, info = recover(journal.path)
            self.assertTrue(info['truncated_tail'])
            self.assertEqual(restored['proofs'], report['proofs'])
            self.assertEqual(restored['rows'], report['rows'])
            self.assertEqual(restored['status'], 'INTERRUPTED')
            self.assertFalse(restored['timing_admission_eligible'])

    def test_proof_mutation_and_removal_are_rejected(self):
        for mutation in ('change', 'remove'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                report = {'status':'RUNNING', 'rows':[], 'candidates':{}, 'proofs':{'first':{'bytes':8}}}
                journal = Journal(Path(directory)/'report.json.gz')
                try:
                    journal.checkpoint(report)
                    changed = copy.deepcopy(report)
                    if mutation == 'change':
                        changed['proofs']['first']['bytes'] = 16
                    else:
                        changed['proofs'].clear()
                    with self.assertRaises(ValueError):
                        journal.checkpoint(changed)
                finally:
                    journal.close()


if __name__ == '__main__':
    unittest.main()
