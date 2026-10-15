"""Contract tests for the host-independent parts of the benchmark runner."""

import importlib.util
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


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

    def test_fixed_frequency_requires_a_matching_host_and_absent_cpufreq(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            fixed, issue = bench.frequency_state(4, "g5g.metal", "aarch64", root)
            self.assertIsNone(issue)
            self.assertEqual(fixed["mode"], "aws_graviton2_hardware_fixed")
            for instance_type, architecture in ((None, "aarch64"),
                                                ("g5g.16xlarge", "aarch64"),
                                                ("g5g.metal", "x86_64")):
                state, issue = bench.frequency_state(4, instance_type, architecture, root)
                self.assertIsNone(state["mode"])
                self.assertIsNotNone(issue)
            freq = root / "cpu4" / "cpufreq"
            freq.mkdir(parents=True)
            state, issue = bench.frequency_state(4, "g5g.metal", "aarch64", root)
            self.assertIsNone(state["mode"])
            self.assertIsNotNone(issue)
            (freq / "scaling_governor").write_text("performance\n")
            (freq / "scaling_min_freq").write_text("2500000\n")
            (freq / "scaling_max_freq").write_text("2500000\n")
            state, issue = bench.frequency_state(4, None, "x86_64", root)
            self.assertIsNone(issue)
            self.assertEqual(state["mode"], "cpufreq_fixed")
            (freq / "scaling_min_freq").write_text("1000000\n")
            state, issue = bench.frequency_state(4, "g5g.metal", "aarch64", root)
            self.assertIsNone(state["mode"])
            self.assertIsNotNone(issue)

    def test_instance_type_requires_imdsv2_token(self):
        with mock.patch.object(bench.urllib.request, "build_opener") as factory:
            opener = factory.return_value
            opener.open.side_effect = [io.BytesIO(b"test-token"), io.BytesIO(b"g5g.metal")]
            self.assertEqual(bench.ec2_instance_type(), "g5g.metal")
            token_request = opener.open.call_args_list[0].args[0]
            type_request = opener.open.call_args_list[1].args[0]
            self.assertEqual(token_request.get_method(), "PUT")
            self.assertEqual(type_request.get_header("X-aws-ec2-metadata-token"), "test-token")
            self.assertEqual(factory.call_args.args[0].proxies, {})
            opener.open.side_effect = OSError("IMDS unavailable")
            self.assertIsNone(bench.ec2_instance_type())

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

    def test_tier1_manifest_is_explicit_and_receipt_is_hashed(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            receipt = root / "allocation.json"
            receipt.write_text('{"provider":"runpod","id":"pod-1"}\n')
            manifest = {"schema": 1, "measurement_tier": "tier1_instance",
                        "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "internal online_ms",
                        "pair_fields": ["target_x"], "result_field": "scalar",
                        "artifacts": [str(binary), str(receipt)],
                        "allocation": {"provider": "runpod", "instance_id": "pod-1",
                                       "receipt": str(receipt)},
                        "isolation": {"cpus": "4", "execution_cpu": 4},
                        "cases": [{"id": "t0", "expected_fields": {"target_x": "9"},
                                   "expected_result": "7", "reference": [str(binary)],
                                   "candidate": [str(binary)]}]}
            self.assertEqual(bench.require_manifest(manifest), ({4}, set(), None))
            for change in (lambda m: m["artifacts"].remove(str(receipt)),
                           lambda m: m["isolation"].update({"cgroup": "/sys/fs/cgroup/bench"}),
                           lambda m: m.pop("allocation"),
                           lambda m: m.update({"measurement_tier": "tier2"})):
                altered = copy.deepcopy(manifest)
                change(altered)
                with self.assertRaises(ValueError):
                    bench.require_manifest(altered)

    def test_tier1_counter_events_invalidate_and_irq_is_observed(self):
        before = {"cpu_stat": {"nr_throttled": 0},
                  "memory_events": {"oom": 0},
                  "per_cpu": {4: {"irq": 0, "softirq": 0, "steal": 0}}}
        after = copy.deepcopy(before)
        after["per_cpu"][4]["irq"] = 1
        self.assertEqual(bench.tier1_noise(before, after), [])
        after["cpu_stat"]["nr_throttled"] = 1
        after["memory_events"]["oom"] = 1
        self.assertEqual(len(bench.tier1_noise(before, after)), 2)

    def test_tier1_preflight_checks_container_cpuset_with_pinned_service(self):
        manifest = {"isolation": {"execution_cpu": 13},
                    "allocation": {"provider": "runpod", "instance_id": "pod-1"}}
        counters = {"per_cpu": {13: {}}, "cpu_stat": {"nr_throttled": 0},
                    "memory_events": {"oom": 0}}
        effective = "2,13"

        def fake_read(path):
            return effective if str(path).endswith("cpuset.cpus.effective") else None

        with (mock.patch.object(bench, "require_manifest", return_value=({13}, set(), None)),
              mock.patch.object(bench, "host_probe", return_value={"affinity": [2]}),
              mock.patch.object(bench, "tier1_cgroup", return_value=bench.CGROUP_ROOT),
              mock.patch.object(bench, "tier1_counters", return_value=counters),
              mock.patch.object(bench, "read", side_effect=fake_read),
              mock.patch.object(bench.sys, "platform", "linux")):
            result = bench.preflight_tier1(manifest)
            self.assertTrue(result["ok"], result["problems"])
            self.assertEqual(result["evidence"]["container_effective_cpus"], [2, 13])
            effective = "2"
            self.assertIn("execution CPU is outside container effective cpuset",
                          bench.preflight_tier1(manifest)["problems"])
            effective = ""
            self.assertIn("container effective cpuset unavailable",
                          bench.preflight_tier1(manifest)["problems"])

    def test_tier1_requires_repeated_consistent_pairs_for_claim(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            binary = root / "bench"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            receipt = root / "allocation.json"
            receipt.write_text("{}\n")
            manifest = {"schema": 1, "measurement_tier": "tier1_instance",
                        "workdir": str(root), "timeout_s": 1,
                        "measurement_boundary": "internal online_ms",
                        "pair_fields": ["target_x"], "result_field": "scalar",
                        "artifacts": [str(binary), str(receipt)],
                        "allocation": {"provider": "runpod", "instance_id": "pod-1",
                                       "receipt": str(receipt)},
                        "isolation": {"cpus": "4", "execution_cpu": 4},
                        "repetitions": 8,
                        "cases": [{"id": "t0", "expected_fields": {"target_x": "9"},
                                   "expected_result": "7", "reference": [str(binary), "reference"],
                                   "candidate": [str(binary), "candidate"]}]}
            original_preflight, original_run = bench.preflight, bench.one_run
            try:
                bench.preflight = lambda _: {"ok": True, "problems": [], "evidence": {}}
                def fake_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                    return {"serial": serial, "status": "valid", "issues": [],
                            "online_ms": 2.0 if argv[-1] == "reference" else 1.0,
                            "fields": {"target_x": "9", "scalar": "7"}}
                bench.one_run = fake_run
                result = bench.execute(manifest, root / "passing")
                self.assertEqual(result["measurement_tier"], "tier1_instance")
                self.assertTrue(result["speedup_claim_eligible"])
                self.assertGreater(result["tier1_bootstrap95_by_pair"][0], 1)
                manifest["repetitions"] = 4
                result = bench.execute(manifest, root / "too_few")
                self.assertFalse(result["speedup_claim_eligible"])
                manifest["repetitions"] = 8
                def mixed_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial):
                    row = fake_run(argv, _manifest, _cpus, _nodes, _cgroup, _folder, serial)
                    if argv[-1] == "candidate" and serial > 8:
                        row["online_ms"] = 4.0
                    return row
                bench.one_run = mixed_run
                result = bench.execute(manifest, root / "mixed")
                self.assertFalse(result["speedup_claim_eligible"])
            finally:
                bench.preflight, bench.one_run = original_preflight, original_run

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
