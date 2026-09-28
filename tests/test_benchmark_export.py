"""Exercise metadata export; never import or run a benchmark harness."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from export_benchmark_snapshot import export


class ExportTest(unittest.TestCase):
    def test_archived_primary_is_complete_and_metadata_only(self):
        data = export(ROOT)
        self.assertEqual(len(data['rows']), 9)
        self.assertEqual(len(data['identities']), 1)
        self.assertEqual(data['rows'][0]['curve_id'], 'EC1N13Ckb1h0f132ba0b5e2')
        self.assertEqual(data['rows'][0]['ic_online_ns'], 33160125)
        self.assertEqual(data['rows'][0]['rho_online_ns'], 320750)
        self.assertNotIn('descents', data['rows'][0])
        self.assertNotIn('scalar', data['rows'][0])

    def test_dirty_input_cannot_claim_commit_provenance(self):
        with patch('export_benchmark_snapshot.subprocess.check_output', side_effect=['a'*40, b'changed']):
            with self.assertRaisesRegex(ValueError, 'differs from the committed'):
                export(ROOT)

if __name__ == '__main__': unittest.main()
