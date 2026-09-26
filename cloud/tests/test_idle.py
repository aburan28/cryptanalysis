import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))
import idle  # noqa: E402

METRICS = """\
# HELP cursor_self_hosted_worker_connected Whether the worker is connected
cursor_self_hosted_worker_connected 1
cursor_self_hosted_worker_session_active 0
cursor_self_hosted_worker_last_activity_unix_seconds 1790380186
cursor_self_hosted_worker_session_ends_total{reason="stream_end"} 0
"""


class MetricsTest(unittest.TestCase):
    def test_parse_the_worker_gauges(self):
        self.assertEqual(idle.parse_metrics(METRICS),
                         {"connected": 1.0, "session_active": 0.0, "last_activity": 1790380186.0})

    def test_only_an_open_session_is_busy(self):
        self.assertEqual(idle.agent_busy({"session_active": 1.0}), "agent session")
        # Heartbeats keep last_activity current even with no agent at all.
        self.assertIsNone(idle.agent_busy({"session_active": 0.0, "last_activity": 1790380186.0}))
        self.assertIsNone(idle.agent_busy({}))


class EditTest(unittest.TestCase):
    def test_files_written_before_since_are_not_edits(self):
        import os
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "a.c")
            path.write_text("x")
            self.assertTrue(idle.recent_edit(root))
            self.assertFalse(idle.recent_edit(root, since=time.time() + 1))
            later = time.time() + 5
            os.utime(path, (later, later))
            self.assertTrue(idle.recent_edit(root, since=later - 1))


if __name__ == "__main__":
    unittest.main()
