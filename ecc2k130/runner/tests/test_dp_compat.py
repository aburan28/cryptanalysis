import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("dp_compat", Path(__file__).resolve().parents[1] / "dp_compat.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CutoffReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source.bin"
        self.dest = Path(self.tmp.name) / "target.bin"
        self.config = {"curve": 131, "walkId": "frozen-walk", "recordFormat": "gpu-packed32", "dpWeight": 34}
        self.rows = [struct.pack("<4Q", 100+i, (1 << weight)-1, 0, 0) for i, weight in enumerate((30,32,34))]
        self.source.write_bytes(b"".join(self.rows))

    def test_retains_seeds_and_endpoint_bytes_at_stricter_cutoff(self):
        result = module.reconcile(self.source,self.dest,self.config,{**self.config,"dpWeight":32})
        self.assertEqual(self.dest.read_bytes(),b"".join(self.rows[:2]))
        self.assertEqual(self.source.read_bytes(),b"".join(self.rows))
        self.assertEqual((result['retained_records'],result['not_retained_records']),(2,1))

    def test_rejects_different_walk_and_leaves_no_output(self):
        with self.assertRaisesRegex(ValueError,'walkId'):
            module.reconcile(self.source,self.dest,self.config,{**self.config,"walkId":"other","dpWeight":32})
        self.assertFalse(self.dest.exists())

    def test_partial_input_is_not_published(self):
        self.source.write_bytes(b"".join(self.rows)+b"x")
        with self.assertRaisesRegex(ValueError,'partial'):
            module.reconcile(self.source,self.dest,self.config,{**self.config,"dpWeight":32})
        self.assertFalse(self.dest.exists())

    def test_incorrect_source_cutoff_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'source cutoff'):
            module.reconcile(self.source,self.dest,{**self.config,"dpWeight":32},{**self.config,"dpWeight":30})
        self.assertFalse(self.dest.exists())

    def test_existing_destination_is_preserved(self):
        self.dest.write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError,'new file'):
            module.reconcile(self.source,self.dest,self.config,{**self.config,"dpWeight":32})
        self.assertEqual(self.dest.read_bytes(),b"keep")

    def test_widening_does_not_claim_to_reconstruct_missing_endpoints(self):
        with self.assertRaisesRegex(ValueError,'no larger'):
            module.reconcile(self.source,self.dest,{**self.config,"dpWeight":32},self.config)
