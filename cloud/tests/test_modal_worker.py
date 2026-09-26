import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import modal_worker
except ImportError:  # the Modal client is not installed
    modal_worker = None


@unittest.skipIf(modal_worker is None, "the Modal client is not installed")
class ModalWorkerTest(unittest.TestCase):
    def test_rate_uses_the_list_prices(self):
        self.assertAlmostEqual(modal_worker.rate(16, 64, None), 16 * 0.0473 + 64 * 0.008)
        self.assertAlmostEqual(modal_worker.rate(4, 32, "RTX-PRO-6000"), 4 * 0.0473 + 32 * 0.008 + 3.03)
        self.assertAlmostEqual(modal_worker.rate(0, 0, "H100:2"), 2 * 3.95)

    def test_sign_in_files_move_between_homes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            (Path(a) / ".config" / "cursor").mkdir(parents=True)
            (Path(a) / ".config" / "cursor" / "auth.json").write_text('{"token": 1}')
            (Path(a) / ".config" / "other.json").write_text("{}")
            self.assertEqual(modal_worker.copy_sign_in(a, b), 1)
            self.assertEqual((Path(b) / ".config" / "cursor" / "auth.json").read_text(), '{"token": 1}')
            self.assertFalse((Path(b) / ".config" / "other.json").exists())
            self.assertEqual(modal_worker.copy_sign_in(Path(a) / "absent", b), 0)

    def test_control_keys_are_not_workers(self):
        entries = {"modal-cpu-1": {"state": "connected"}, "modal-cpu-1:stop": True}
        self.assertEqual(list(modal_worker.worker_entries(entries)), ["modal-cpu-1"])

    def test_command_line(self):
        calls = []
        with mock.patch.object(modal_worker, "cmd_up", side_effect=lambda a: calls.append(a) or 0):
            modal_worker.main(["up", "modal-gpu-1", "--gpu", "RTX-PRO-6000", "--cpu", "4",
                               "--memory", "32", "--idle-minutes", "60"])
        args = calls[0]
        self.assertEqual((args.names, args.gpu, args.cpu, args.memory, args.idle_minutes),
                         (["modal-gpu-1"], "RTX-PRO-6000", 4.0, 32.0, 60.0))
        for bad in (["up", "a b"], ["up", "w", "--hours", "25"], ["down"]):
            with self.assertRaises(SystemExit):
                modal_worker.main(bad)


if __name__ == "__main__":
    unittest.main()
