"""Contract tests for the host-independent parts of the benchmark runner."""

import contextlib
import importlib.util
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "isolated_bench.py"
GENERATOR = SOURCE.with_name("make_j0_isolated_manifest.py")
SPEC = importlib.util.spec_from_file_location("isolated_bench", SOURCE)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class IsolatedBenchTests(unittest.TestCase):
    def test_arm_cpu_identity_fallback(self):
        cpuinfo = "processor: 0\nCPU implementer: 0x61\nCPU architecture: 8\nCPU part: 0x000\n"
        with mock.patch.object(bench, "read", return_value=cpuinfo):
            self.assertEqual(bench.cpu_identity(), "ARM 0x61/8/0x000")

    def tier1_manifest(self, root):
        binary = root / "bench"
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o755)
        allocation = root / "allocation.json"
        allocation.write_text(json.dumps({"provider": "runpod", "instance_id": "pod-123"}))
        return {"schema": 1, "workdir": str(root), "timeout_s": 1,
                "repetitions": 5, "measurement_boundary": "internal online_ms",
                "pair_fields": ["target_x"], "result_field": "scalar",
                "artifacts": [str(binary), str(allocation)],
                "isolation": {"tier": "tier1", "cpus": "4", "execution_cpu": 4,
                              "mem_nodes": "0", "cgroup": "/sys/fs/cgroup",
                              "allocation": {"provider": "runpod", "instance_id": "pod-123",
                                             "receipt": str(allocation)}},
                "cases": [{"id": "t0", "expected_fields": {"target_x": "9"},
                           "expected_result": "7", "reference": [str(binary), "reference"],
                           "candidate": [str(binary), "candidate"]}]}

    def test_tier1_manifest_binds_allocation_and_repeated_one_cpu_case(self):
        with tempfile.TemporaryDirectory() as dirname:
            manifest = self.tier1_manifest(Path(dirname))
            bench.require_manifest(manifest)
            missing = copy.deepcopy(manifest)
            missing["artifacts"].pop()
            with self.assertRaisesRegex(ValueError, "hash-bound"):
                bench.require_manifest(missing)
            wrong = copy.deepcopy(manifest)
            wrong["isolation"]["allocation"]["instance_id"] = "pod-other"
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                bench.require_manifest(wrong)
            short = copy.deepcopy(manifest)
            short["repetitions"] = 4
            with self.assertRaisesRegex(ValueError, "five alternating"):
                bench.require_manifest(short)
            multi_cpu = copy.deepcopy(manifest)
            multi_cpu["isolation"]["cpus"] = "4-5"
            with self.assertRaisesRegex(ValueError, "one pinned"):
                bench.require_manifest(multi_cpu)

    def test_tier1_preflight_uses_exposed_cpu_and_current_cgroup(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            cgroup = root / "pod"
            cgroup.mkdir()
            manifest = self.tier1_manifest(root)
            manifest["isolation"]["cgroup"] = str(cgroup)
            files = {"cpuset.cpus.effective": "4-5", "cpu.stat": "nr_throttled 0\nthrottled_usec 0",
                     "memory.events": "max 0\noom 0\noom_kill 0", "cpu.max": "max 100000",
                     "memory.max": "8589934592", "cpu.pressure": "some avg10=0 total=0",
                     "memory.current": "1024", "thread_siblings_list": "4-5"}
            original_root = bench.CGROUP_ROOT
            bench.CGROUP_ROOT = root
            try:
                with mock.patch.object(bench, "read", side_effect=lambda path: files.get(Path(path).name)), \
                     mock.patch.object(bench, "current_cgroup", return_value=cgroup.resolve()), \
                     mock.patch.object(bench, "virtualization", return_value="docker"), \
                     mock.patch.object(bench.os, "sched_getaffinity", return_value={4, 5}, create=True), \
                     mock.patch.object(bench, "counters", return_value={"per_cpu": {4: {"steal": 0}}}):
                    evidence = {"topology": {}, "frequency": {}, "cpu_model": "test CPU"}
                    health = bench.tier1_preflight(manifest, {4}, cgroup, evidence)
                    self.assertTrue(health["ok"], health["problems"])
                    self.assertFalse(health["evidence"]["host_exclusivity_proved"])
                    with mock.patch.object(bench, "current_cgroup", return_value=root):
                        wrong = bench.tier1_preflight(manifest, {4}, cgroup,
                                                       {"topology": {}, "frequency": {},
                                                        "cpu_model": "test CPU"})
                    self.assertFalse(wrong["ok"])
                    self.assertTrue(any("current cgroup" in p for p in wrong["problems"]))
            finally:
                bench.CGROUP_ROOT = original_root

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
        tier1_issues = bench.noise(before, after, u0, u1, "tier1")
        self.assertTrue(any("throttling" in issue for issue in tier1_issues))
        self.assertTrue(any("steal" in issue for issue in tier1_issues))
        self.assertFalse(any("interrupt count" in issue for issue in tier1_issues))
        self.assertFalse(any("context switches" in issue for issue in tier1_issues))
        capped = copy.deepcopy(before)
        capped["memory_events"]["max"] = 0
        capped_after = copy.deepcopy(capped)
        capped_after["memory_events"]["max"] = 1
        self.assertIn("memory event: max",
                      bench.noise(capped, capped_after, u0, u0, "tier1"))

    def test_tier1_speedup_needs_paired_interval_above_one(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            manifest = self.tier1_manifest(root)
            original_preflight, original_run = bench.preflight, bench.one_run
            bench.preflight = lambda _: {"ok": True, "tier": "tier1",
                                         "problems": [], "evidence": {}}
            try:
                for name, ratios in (("strong", [2.0] * 5),
                                     ("mixed", [2.0, 1.5, 1.1, 0.8, 0.7])):
                    def fake_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                        ratio = ratios[(serial - 1) // 2]
                        metric = ratio if argv[-1] == "reference" else 1.0
                        return {"serial": serial, "status": "valid", "issues": [],
                                "metric_ms": metric, "online_ms": metric,
                                "fields": {"target_x": "9", "scalar": "7"}}
                    bench.one_run = fake_run
                    summary = bench.execute(manifest, root / name)
                    self.assertEqual(summary["status"], "completed")
                    self.assertEqual(summary["tier"], "tier1")
                    self.assertEqual(summary["provider"], "runpod")
                    self.assertIsNotNone(summary["bootstrap95_by_pair"])
                    if name == "strong":
                        self.assertTrue(summary["speedup_qualified"])
                        self.assertEqual(summary["paired_speedup"], 2.0)
                    else:
                        self.assertFalse(summary["speedup_qualified"])
                        self.assertIsNone(summary["paired_speedup"])
                        self.assertIsNotNone(summary["observed_ratio_median"])
            finally:
                bench.preflight, bench.one_run = original_preflight, original_run

    def test_pair_fields_and_single_worker(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            manifest = {"schema": 1, "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "self reported online_ms",
                        "pair_fields": ["target_x"], "result_field": "scalar",
                        "artifacts": [str(binary)],
                        "isolation": {"cpus": "4", "execution_cpu": 4, "mem_nodes": "0",
                                      "cgroup": "/sys/fs/cgroup/bench"},
                        "cases": [{"id": "t0", "expected_fields": {"target_x": "9"},
                                   "expected_result": "7",
                                   "reference": [str(binary)],
                                   "candidate": [str(binary)]}]}
            bench.require_manifest(manifest)
            manifest["metric_field"] = "prep_ms"
            with self.assertRaises(ValueError):
                bench.require_manifest(manifest)
            manifest["measurement_kind"] = "table_preparation"
            bench.require_manifest(manifest)
            manifest["metric_field"] = "../prep_ms"
            with self.assertRaises(ValueError):
                bench.require_manifest(manifest)
            manifest.pop("metric_field")
            manifest.pop("measurement_kind")
            manifest["cases"][0]["candidate"].append("7")
            with self.assertRaises(ValueError):
                bench.require_manifest(manifest)
            manifest["cases"][0]["candidate"].pop()
            manifest["pair_fields"] = []
            with self.assertRaises(ValueError):
                bench.require_manifest(manifest)
            old_lock = bench.HOST_LOCK_PATH
            bench.HOST_LOCK_PATH = root / "host.lock"
            try:
                with bench.only_worker(root):
                    with self.assertRaises(RuntimeError):
                        with bench.only_worker(root):
                            pass
            finally:
                bench.HOST_LOCK_PATH = old_lock

    def test_output_parser_uses_timed_row(self):
        fields = bench.output_fields("setup\ncurve=c online_ms=12.5 verified=1 target_x=9\ndone")
        self.assertEqual(fields["online_ms"], "12.5")
        self.assertEqual(fields["target_x"], "9")
        prep = bench.output_fields("setup\ncurve=c prep_ms=4.5 verified=1\ndone",
                                   "prep_ms")
        self.assertEqual(prep["prep_ms"], "4.5")

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
                        "pair_fields": ["target_x"], "result_field": "scalar",
                        "artifacts": [str(executable)],
                        "isolation": {"cpus": "99999", "execution_cpu": 99999,
                                      "mem_nodes": "0", "cgroup": "/sys/fs/cgroup/no-such-partition"},
                        "cases": [{"id": "t0", "expected_fields": {"target_x": "9"},
                                   "expected_result": "7",
                                   "reference": [str(executable)],
                                   "candidate": [str(executable)]}]}
            db = bench.database(root)
            for job_id in ("a", "b"):
                db.execute("INSERT INTO jobs(id,status,created_ns,manifest) VALUES(?,?,?,?)",
                           (job_id, "queued", 1 if job_id == "a" else 2,
                            json.dumps(manifest)))
            db.close()
            old_lock = bench.HOST_LOCK_PATH
            bench.HOST_LOCK_PATH = root / "host.lock"
            try:
                bench.serve(root, once=True)
            finally:
                bench.HOST_LOCK_PATH = old_lock
            db = bench.database(root)
            self.assertEqual(db.execute("SELECT status FROM jobs WHERE id='a'").fetchone()[0], "rejected")
            self.assertEqual(db.execute("SELECT status FROM jobs WHERE id='b'").fetchone()[0], "queued")
            self.assertFalse(marker.exists())
            self.assertFalse((root / "results" / "a" / "runs.jsonl").exists())

    def test_shared_job_lock_waits_for_other_launcher(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            lock_path = root / "experiment-runs.lock"
            db = bench.database(root)
            db.execute("INSERT INTO jobs(id,status,created_ns,manifest) VALUES(?,?,?,?)",
                       ("a", "queued", 1, "{}"))
            db.close()
            entered = threading.Event()
            started = threading.Event()
            original_execute = bench.execute
            original_host_lock = bench.HOST_LOCK_PATH
            original_job_slot = bench.job_slot

            def fake_execute(_manifest, _output):
                started.set()
                return {"status": "rejected"}

            @contextlib.contextmanager
            def observed_job_slot(path):
                entered.set()
                with original_job_slot(path):
                    yield

            bench.execute = fake_execute
            bench.job_slot = observed_job_slot
            bench.HOST_LOCK_PATH = root / "host.lock"
            worker = threading.Thread(target=bench.serve,
                                      args=(root,),
                                      kwargs={"once": True, "shared_job_lock": lock_path})
            try:
                with lock_path.open("a+") as other_launcher:
                    fcntl.flock(other_launcher, fcntl.LOCK_EX)
                    worker.start()
                    self.assertTrue(entered.wait(2))
                    worker.join(0.2)
                    self.assertTrue(worker.is_alive())
                    self.assertFalse(started.is_set())
                    check = bench.database(root)
                    self.assertEqual(check.execute("SELECT status FROM jobs WHERE id='a'")
                                     .fetchone()[0], "queued")
                    check.close()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertTrue(started.is_set())
                check = bench.database(root)
                self.assertEqual(check.execute("SELECT status FROM jobs WHERE id='a'")
                                 .fetchone()[0], "rejected")
                check.close()
            finally:
                if worker.ident is not None:
                    worker.join(2)
                bench.execute = original_execute
                bench.HOST_LOCK_PATH = original_host_lock
                bench.job_slot = original_job_slot

    def test_shared_wrong_target_or_answer_cannot_produce_speedup(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            manifest = {"schema": 1, "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "internal online_ms",
                        "pair_fields": ["target_x"], "result_field": "scalar",
                        "artifacts": [str(binary)],
                        "isolation": {"cpus": "4", "execution_cpu": 4,
                                      "mem_nodes": "0", "cgroup": "/sys/fs/cgroup/bench"},
                        "cases": [{"id": "t0", "expected_fields": {"target_x": "1"},
                                   "expected_result": "7",
                                   "reference": [str(binary), "reference"],
                                   "candidate": [str(binary), "candidate"]}]}
            original_preflight, original_run = bench.preflight, bench.one_run
            try:
                bench.preflight = lambda _: {"ok": True, "problems": [], "evidence": {}}
                for wrong in ("target", "answer", "none"):
                    def fake_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                        reference = argv[-1] == "reference"
                        return {"serial": serial, "status": "valid", "issues": [],
                                "online_ms": 2.0 if reference else 1.0,
                                "fields": {"target_x": "2" if wrong == "target" else "1",
                                           "scalar": "8" if wrong == "answer" else "7"}}
                    bench.one_run = fake_run
                    summary = bench.execute(manifest, root / wrong)
                    pair = json.loads((root / wrong / "pairs.jsonl").read_text())
                    if wrong == "none":
                        self.assertEqual(summary["status"], "completed")
                        self.assertEqual(summary["paired_speedup"], 2.0)
                        self.assertEqual(pair["status"], "valid")
                    else:
                        self.assertEqual(summary["status"], "invalid")
                        self.assertIsNone(summary["paired_speedup"])
                        self.assertEqual(pair["status"], "invalid")
                        self.assertIn("target_x" if wrong == "target" else "expected_result",
                                      pair["issues"][0])
                manifest["metric_field"] = "prep_ms"
                manifest["measurement_kind"] = "table_preparation"
                def fake_prep_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder,
                                  serial):
                    reference = argv[-1] == "reference"
                    return {"serial": serial, "status": "valid", "issues": [],
                            "online_ms": None,
                            "metric_ms": 3.0 if reference else 1.0,
                            "fields": {"target_x": "1", "scalar": "7"}}
                bench.one_run = fake_prep_run
                summary = bench.execute(manifest, root / "preparation")
                self.assertEqual(summary["paired_speedup"], 3.0)
                self.assertEqual(summary["metric_field"], "prep_ms")
                self.assertEqual(summary["measurement_kind"], "table_preparation")
            finally:
                bench.preflight, bench.one_run = original_preflight, original_run

    def test_j0_manifest_passes_only_public_target_to_solver(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "fixture"
            binary.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "assert sys.argv[1] == '--print-target'\n"
                "print('curve=' + sys.argv[2] + ' p=2305843009213693951 b=5 '"
                "'order=51131959441 base_x=1 base_y=2 '"
                "'target_x=987654321 target_y=123456789 '"
                "'fixture_scalar=' + sys.argv[3])\n")
            binary.chmod(0o755)
            for name in ("CMakeLists.txt", "src/curve.c", "src/ec_tau.c",
                         "experiments/prime-j0-tau-20260930/large-rho-20261002/bench_rho_large.c",
                         "scripts/make_j0_isolated_manifest.py", "scripts/isolated_bench.py"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n")
            output = root / "panel.json"
            subprocess.run(
                [sys.executable, str(GENERATOR), "--reference", str(binary),
                 "--candidate", str(binary), "--workdir", str(root),
                 "--cgroup", "/sys/fs/cgroup/benchmark-isolated",
                 "--cpus", "4-5", "--execution-cpu", "4", "--mem-nodes", "0",
                 "--targets-36", "1", "--targets-37", "0", "--targets-46", "0",
                 "--output", str(output)],
                check=True, capture_output=True, text=True)
            manifest = json.loads(output.read_text())
            bench.require_manifest(manifest)
            case = manifest["cases"][0]
            self.assertEqual(case["expected_fields"]["target_x"], "987654321")
            self.assertEqual(case["reference"], case["candidate"])
            self.assertEqual(case["reference"][1:4],
                             ["--public-target", "j0-36", "1"])
            self.assertNotIn(case["expected_result"], case["reference"])


if __name__ == "__main__":
    unittest.main()
