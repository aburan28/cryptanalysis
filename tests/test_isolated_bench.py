"""Contract tests for the host-independent parts of the benchmark runner."""

import importlib.util
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "isolated_bench.py"
SPEC = importlib.util.spec_from_file_location("isolated_bench", SOURCE)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class IsolatedBenchTests(unittest.TestCase):
    def test_cpu_ranges_and_invalid_ranges(self):
        self.assertEqual(bench.cpu_set("1,3-5,4"), {1, 3, 4, 5})
        self.assertEqual(bench.format_set({5, 1, 3}), "1,3,5")
        for bad in ("", "-1", "5-3", "1-2-3"):
            with self.assertRaises(ValueError):
                bench.cpu_set(bad)

    def test_noise_invalidates_throttle_irq_steal_and_switch(self):
        before = {"cpu_stat": {"nr_throttled": 0, "throttled_usec": 0},
                  "memory_events": {"oom": 0, "oom_kill": 0},
                  "cpu_pressure_total": {"some": 0},
                  "per_cpu": {4: {"irq": 0, "softirq": 0, "steal": 0}},
                  "interrupts": {4: 100},
                  "thermal_throttle": {4: {"core_throttle_count": None,
                                           "package_throttle_count": None}},
                  "frequency_khz": {4: "1000000"}}
        after = copy.deepcopy(before)
        after["per_cpu"] = {4: {"irq": 0, "softirq": 0, "steal": 1}}
        after["interrupts"] = {4: 101}
        after["cpu_stat"]["nr_throttled"] = 1
        usage = type("Usage", (), {})
        u0, u1 = usage(), usage()
        u0.ru_nivcsw, u1.ru_nivcsw = 0, 1
        u0.ru_majflt, u1.ru_majflt = 0, 0
        issues = bench.noise(before, after, u0, u1)
        self.assertTrue(any("throttling" in issue for issue in issues))
        self.assertTrue(any("interrupt count" in issue for issue in issues))
        self.assertTrue(any("steal" in issue for issue in issues))
        self.assertTrue(any("context switches" in issue for issue in issues))

    def test_pair_fields_and_single_worker(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            manifest = {"schema": 1, "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "self reported online_ms",
                        "pair_fields": ["target_x"],
                        "artifacts": [str(binary)],
                        "isolation": {"cpus": "4", "execution_cpu": 4, "mem_nodes": "0",
                                      "cgroup": "/sys/fs/cgroup/bench"},
                        "cases": [{"id": "t0", "reference": [str(binary)],
                                   "candidate": [str(binary)]}]}
            bench.require_manifest(manifest)
            manifest["pair_fields"] = []
            with self.assertRaises(ValueError):
                bench.require_manifest(manifest)
            with bench.only_worker(root):
                with self.assertRaises(RuntimeError):
                    with bench.only_worker(root):
                        pass

    def test_output_parser_uses_timed_row(self):
        fields = bench.output_fields("setup\ncurve=c online_ms=12.5 verified=1 target_x=9\ndone")
        self.assertEqual(fields["online_ms"], "12.5")
        self.assertEqual(fields["target_x"], "9")

    def test_provisioning_key_is_not_in_benchmark_environment(self):
        previous = os.environ.get("RUNPOD_API_KEY")
        try:
            os.environ["RUNPOD_API_KEY"] = "test-only-key"
            self.assertNotIn("RUNPOD_API_KEY", bench.benchmark_env())
        finally:
            if previous is None:
                del os.environ["RUNPOD_API_KEY"]
            else:
                os.environ["RUNPOD_API_KEY"] = previous

    def test_rejected_host_never_launches_and_queue_is_serial(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            executable = root / "bench"
            marker = root / "executed"
            executable.write_text("#!/bin/sh\ntouch '" + str(marker) + "'\n")
            executable.chmod(0o755)
            manifest = {"schema": 1, "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "internal online_ms",
                        "pair_fields": ["target_x"],
                        "artifacts": [str(executable)],
                        "isolation": {"cpus": "99999", "execution_cpu": 99999,
                                      "mem_nodes": "0", "cgroup": "/sys/fs/cgroup/no-such-partition"},
                        "cases": [{"id": "t0", "reference": [str(executable)],
                                   "candidate": [str(executable)]}]}
            db = bench.database(root)
            for job_id in ("a", "b"):
                db.execute("INSERT INTO jobs(id,status,created_ns,manifest) VALUES(?,?,?,?)",
                           (job_id, "queued", 1 if job_id == "a" else 2,
                            json.dumps(manifest)))
            db.close()
            bench.serve(root, once=True)
            db = bench.database(root)
            self.assertEqual(db.execute("SELECT status FROM jobs WHERE id='a'").fetchone()[0], "rejected")
            self.assertEqual(db.execute("SELECT status FROM jobs WHERE id='b'").fetchone()[0], "queued")
            self.assertFalse(marker.exists())
            self.assertFalse((root / "results" / "a" / "runs.jsonl").exists())

    def test_pair_mismatch_cannot_produce_speedup(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            manifest = {"schema": 1, "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "internal online_ms",
                        "pair_fields": ["target_x"],
                        "artifacts": [str(binary)],
                        "isolation": {"cpus": "4", "execution_cpu": 4,
                                      "mem_nodes": "0", "cgroup": "/sys/fs/cgroup/bench"},
                        "cases": [{"id": "t0", "reference": [str(binary), "reference"],
                                   "candidate": [str(binary), "candidate"]}]}
            original_preflight, original_run = bench.preflight, bench.one_run
            try:
                bench.preflight = lambda _: {"ok": True, "problems": [], "evidence": {}}
                def fake_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                    reference = argv[-1] == "reference"
                    return {"serial": serial, "status": "valid", "issues": [],
                            "online_ms": 2.0 if reference else 1.0,
                            "fields": {"target_x": "1" if reference else "2"}}
                bench.one_run = fake_run
                summary = bench.execute(manifest, root / "result")
            finally:
                bench.preflight, bench.one_run = original_preflight, original_run
            self.assertEqual(summary["status"], "invalid")
            self.assertIsNone(summary["paired_speedup"])
            pair = json.loads((root / "result" / "pairs.jsonl").read_text())
            self.assertEqual(pair["status"], "invalid")
            self.assertIn("target_x", pair["issues"][0])


if __name__ == "__main__":
    unittest.main()
