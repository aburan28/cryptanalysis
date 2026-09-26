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

    def test_an_active_session_is_busy(self):
        self.assertEqual(idle.agent_busy({"session_active": 1.0}), "agent session")

    def test_recent_activity_is_busy_and_old_activity_is_not(self):
        now = 1790380186.0 + 60
        self.assertEqual(idle.agent_busy({"session_active": 0.0, "last_activity": 1790380186.0}, now),
                         "recent agent activity")
        self.assertIsNone(idle.agent_busy({"session_active": 0.0, "last_activity": 1790380186.0},
                                          now + idle.ACTIVITY_WINDOW_SECONDS))
        self.assertIsNone(idle.agent_busy({}))


if __name__ == "__main__":
    unittest.main()
