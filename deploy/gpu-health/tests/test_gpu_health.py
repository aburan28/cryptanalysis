"""Tests for gpu_health.py against scripted stand-ins for ec2k-gpu and nvidia-smi.

No GPU is needed: tests/fakes/ec2k-gpu prints what the real binary prints for
a scenario, and tests/fakes/nvidia-smi answers as a driver would, including
while a fake load is running.  What these tests hold is the orchestrator:
that each kind of bad GPU fails for the reason it should, and a good one
passes.  What the real binary checks on a card is ecc2k130/src/hosttest.cpp's
business, and whether a card is healthy is the card's.

    python3 -m unittest discover -s deploy/gpu-health/tests -v
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import gpu_health  # noqa: E402

FAKES = os.path.join(HERE, "fakes")
H100 = "NVIDIA H100 80GB HBM3"


def gpu(index, **kw):
    g = {"name": H100, "uuid": "GPU-%08d-0000-0000-0000-000000000000" % index, "sms": 132,
         "cc": "9.0", "rate": 7.5e9}
    g.update(kw)
    return g


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = dict(os.environ)
        os.environ["FAKE_GPU_STATE"] = self.tmp.name
        os.environ.pop("NODE_NAME", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def run_check(self, scenario, *extra, smi=True, api=None):
        path = os.path.join(self.tmp.name, "scenario.json")
        with open(path, "w") as f:
            json.dump(scenario, f)
        os.environ["FAKE_GPU_SCENARIO"] = path
        term = os.path.join(self.tmp.name, "termination-log")
        args = ["--binary", os.path.join(FAKES, "ec2k-gpu"),
                "--nvidia-smi", os.path.join(FAKES, "nvidia-smi") if smi else "/nonexistent/smi",
                "--seconds", "0.4", "--sample-interval", "0.05", "--setup-allowance", "2",
                "--kill-grace", "0.5", "--termination-log", term, "--quiet"] + list(extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = gpu_health.main(args, **({"api": api} if api else {}))
        lines = out.getvalue().strip().splitlines()
        report = json.loads(lines[-1]) if lines else None
        with open(term) as f:
            self.termination = f.read()
        self.stderr = err.getvalue()
        return rc, report

    def failures(self, report, index):
        return " | ".join(report["gpus"][index]["failures"])

    def warnings(self, report, index):
        return " | ".join(report["gpus"][index]["warnings"])

    # ---- healthy ------------------------------------------------------------

    def test_healthy_node_passes(self):
        rc, report = self.run_check({"gpus": [gpu(0), gpu(1)]})
        self.assertEqual(rc, 0, report)
        self.assertEqual(report["verdict"], "pass")
        self.assertTrue(self.termination.startswith("PASS 2/2 GPU(s) healthy"), self.termination)
        g = report["gpus"][0]
        self.assertEqual(g["throughput"]["peerRatio"], 1.0)
        self.assertGreater(g["telemetry"]["samples"], 0)
        self.assertEqual(g["telemetry"]["powerMaxW"], 520.0)
        self.assertIn("no baseline", " ".join(g["notes"]))

    def test_rewalk_threads_follow_the_cpus(self):
        rc, report = self.run_check({"gpus": [gpu(0)]}, "--rewalk-threads", "3")
        self.assertEqual(rc, 0)
        self.assertEqual(report["gpus"][0]["result"]["rewalk"]["threads"], 3)

    # ---- correctness -----------------------------------------------------------

    def test_corrupted_reports_fail_the_gpu_that_made_them(self):
        rc, report = self.run_check({"gpus": [gpu(0), gpu(1, faults={"curve": 3})]})
        self.assertEqual(rc, 1)
        self.assertEqual(report["gpus"][0]["verdict"], "pass")
        self.assertIn("silent data corruption: 3 of 1000 reports", self.failures(report, 1))
        self.assertIn("3 curve", self.failures(report, 1))
        self.assertIn("gpu1", self.termination)

    def test_a_failed_rewalk_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, faults={"rewalk": 1})]})
        self.assertEqual(rc, 1)
        self.assertIn("1 rewalk", self.failures(report, 0))

    def test_inconclusive_run_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, behavior="inconclusive")]})
        self.assertEqual(rc, 1)
        self.assertIn("inconclusive", self.failures(report, 0))

    def test_cuda_error_fails_with_its_message(self):
        rc, report = self.run_check({"gpus": [gpu(0), gpu(1, behavior="crash")]})
        self.assertEqual(rc, 1)
        self.assertIn("died without a result, exit 3", self.failures(report, 1))
        self.assertIn("illegal memory access", self.failures(report, 1))

    def test_a_hung_gpu_is_killed_and_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, behavior="hang")]})
        self.assertEqual(rc, 1)
        self.assertIn("hung", self.failures(report, 0))

    def test_host_self_check_failure_stops_the_run(self):
        rc, report = self.run_check({"hostCheck": "fail", "gpus": [gpu(0)]})
        self.assertEqual(rc, 1)
        self.assertIn("self-check failed", " ".join(report["errors"]))

    # ---- devices ----------------------------------------------------------------

    def test_no_device(self):
        rc, report = self.run_check({"devicesError": "CUDA driver version is insufficient for "
                                                     "CUDA runtime version", "gpus": []})
        self.assertEqual(rc, 1)
        self.assertIn("no usable CUDA device: CUDA driver version is insufficient",
                      " ".join(report["errors"]))

    def test_missing_gpu(self):
        rc, report = self.run_check({"gpus": [gpu(i) for i in range(7)]}, "--expect-gpus", "8")
        self.assertEqual(rc, 1)
        self.assertIn("7 GPU(s) visible, 8 expected", " ".join(report["errors"]))

    def test_pre_ampere_is_unsupported(self):
        rc, report = self.run_check({"gpus": [gpu(0, name="Tesla T4", cc="7.5", sms=40)]})
        self.assertEqual(rc, 1)
        self.assertIn("unsupported: compute capability 7.5", self.failures(report, 0))

    def test_missing_binary_is_a_usage_error(self):
        path = os.path.join(self.tmp.name, "scenario.json")
        with open(path, "w") as f:
            json.dump({"gpus": []}, f)
        os.environ["FAKE_GPU_SCENARIO"] = path
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = gpu_health.main(["--binary", "/nonexistent/ec2k-gpu", "--termination-log", ""])
        self.assertEqual(rc, 2)

    # ---- throughput -------------------------------------------------------------

    def baselines(self, rate, **kw):
        entry = {"name": H100, "sms": 132, "iterationsPerSecond": rate}
        entry.update(kw)
        path = os.path.join(self.tmp.name, "baselines.json")
        with open(path, "w") as f:
            json.dump({"schema": 1, "entries": [entry]}, f)
        return path

    def test_slow_against_baseline_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, rate=6.3e9)]},
                                    "--baselines", self.baselines(7.5e9))
        self.assertEqual(rc, 1)
        self.assertIn("84.0% of the NVIDIA H100 80GB HBM3 baseline", self.failures(report, 0))
        self.assertEqual(report["gpus"][0]["throughput"]["baselineRatio"], 0.84)

    def test_slightly_slow_against_baseline_warns(self):
        rc, report = self.run_check({"gpus": [gpu(0, rate=7.0e9)]},
                                    "--baselines", self.baselines(7.5e9))
        self.assertEqual(rc, 0)
        self.assertIn("93.3% of the", self.warnings(report, 0))
        rc, report = self.run_check({"gpus": [gpu(0, rate=7.0e9)]},
                                    "--baselines", self.baselines(7.5e9), "--strict")
        self.assertEqual(rc, 1)
        self.assertIn("(strict)", self.failures(report, 0))

    def test_baseline_from_another_build_is_advisory(self):
        rc, report = self.run_check({"gpus": [gpu(0, rate=6.0e9)]},
                                    "--baselines", self.baselines(7.5e9, binarySha256="0" * 64))
        self.assertEqual(rc, 0)
        self.assertIn("another ec2k-gpu build", self.warnings(report, 0))

    def test_threshold_override(self):
        rc, _ = self.run_check({"gpus": [gpu(0, rate=7.0e9)]}, "--baselines",
                               self.baselines(7.5e9), "--threshold", "baseline_fail=0.95")
        self.assertEqual(rc, 1)

    def test_slow_peer_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0), gpu(1), gpu(2, rate=6.4e9), gpu(3)]})
        self.assertEqual(rc, 1)
        self.assertEqual([g["verdict"] for g in report["gpus"]], ["pass", "pass", "fail", "pass"])
        self.assertIn("85.3% of the median of the 3 other", self.failures(report, 2))

    def test_peers_are_grouped_by_model(self):
        rc, report = self.run_check({"gpus": [gpu(0), gpu(1, name="NVIDIA L40S", sms=142,
                                                         rate=8.7e9)]})
        self.assertEqual(rc, 0)
        self.assertIsNone(report["gpus"][0]["throughput"]["peerRatio"])

    def test_slowing_under_load_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, trend=0.8)]})
        self.assertEqual(rc, 1)
        self.assertIn("slowing under load", self.failures(report, 0))

    def test_calibrate_prints_baseline_entries(self):
        rc, report = self.run_check({"gpus": [gpu(0, rate=7.4e9), gpu(1, rate=7.6e9),
                                              gpu(2, rate=7.5e9)]}, "--calibrate")
        self.assertEqual(rc, 0)
        entries = report["calibration"]["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], H100)
        self.assertEqual(entries[0]["iterationsPerSecond"], 7500000000)
        self.assertEqual(entries[0]["gpus"], 3)
        self.assertEqual(entries[0]["powerLimitW"], 700.0)
        self.assertEqual(entries[0]["binarySha256"], report["binary"]["sha256"])

    # ---- telemetry --------------------------------------------------------------

    def test_hardware_slowdown_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, smi={"reasons": 0x8 | 0x4})]})
        self.assertEqual(rc, 1)
        self.assertIn("hardware clock slowdown during the load: hw_slowdown",
                      self.failures(report, 0))

    def test_power_brake_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, smi={"reasons": 0x80})]})
        self.assertEqual(rc, 1)
        self.assertIn("hw_power_brake_slowdown", self.failures(report, 0))

    def test_thermal_throttling_warns_and_power_cap_is_a_note(self):
        rc, report = self.run_check({"gpus": [gpu(0, smi={"reasons": 0x20 | 0x4})]})
        self.assertEqual(rc, 0)
        self.assertIn("thermal throttling", self.warnings(report, 0))
        self.assertIn("sw_power_cap", " ".join(report["gpus"][0]["notes"]))

    def test_uncorrectable_ecc_during_load_fails(self):
        smi = {"ecc.errors.uncorrected.volatile.total.after": 2}
        rc, report = self.run_check({"gpus": [gpu(0, smi=smi)]})
        self.assertEqual(rc, 1)
        self.assertIn("2 uncorrectable ECC error(s) during the load", self.failures(report, 0))

    def test_correctable_ecc_during_load_warns(self):
        smi = {"ecc.errors.corrected.volatile.total.after": 5}
        rc, report = self.run_check({"gpus": [gpu(0, smi=smi)]})
        self.assertEqual(rc, 0)
        self.assertIn("5 correctable ECC", self.warnings(report, 0))

    def test_pending_row_remap_fails(self):
        rc, report = self.run_check({"gpus": [gpu(0, remap={"pending": "Yes"})]})
        self.assertEqual(rc, 1)
        self.assertIn("row remap is pending", self.failures(report, 0))

    def test_narrow_pcie_link_warns(self):
        rc, report = self.run_check({"gpus": [gpu(0, smi={"pcie.link.width.current": 8})]})
        self.assertEqual(rc, 0)
        self.assertIn("PCIe link x8, narrower than the GPU's x16", self.warnings(report, 0))

    def test_other_processes_warn(self):
        rc, report = self.run_check({"gpus": [gpu(0, apps=1)]})
        self.assertEqual(rc, 0)
        self.assertIn("other process", self.warnings(report, 0))

    # ---- the node gate ------------------------------------------------------------

    def gate_api(self, tainted=True):
        calls = []
        taints = [{"key": "gpu-health/pending", "value": "true", "effect": "NoSchedule"}]

        def fake(method, path, body=None, content_type=None):
            calls.append((method, path, body))
            if method == "GET":
                return 200, {"metadata": {"resourceVersion": "1"},
                             "spec": {"taints": taints if tainted else []}}
            return 200, {}
        return fake, calls

    def test_gate_lifts_the_taint_after_a_pass(self):
        os.environ["NODE_NAME"] = "gpu-node-1"
        fake, calls = self.gate_api()
        rc, report = self.run_check({"gpus": [gpu(0)]}, "--node-gate", api=fake)
        self.assertEqual(rc, 0)
        patch = [c for c in calls if c[0] == "PATCH"][0]
        self.assertEqual(patch[1], "/api/v1/nodes/gpu-node-1")
        self.assertIsNone(patch[2]["spec"]["taints"])
        self.assertEqual(patch[2]["metadata"]["labels"], {"gpu-health/verdict": "pass"})
        self.assertIn("gpu-health/pending lifted", self.stderr)

    def test_gate_keeps_the_taint_after_a_failure(self):
        os.environ["NODE_NAME"] = "gpu-node-1"
        fake, calls = self.gate_api()
        rc, _ = self.run_check({"gpus": [gpu(0, faults={"curve": 1})]}, "--node-gate", api=fake)
        self.assertEqual(rc, 1)
        patch = [c for c in calls if c[0] == "PATCH"][0]
        self.assertNotIn("spec", patch[2])
        self.assertEqual(patch[2]["metadata"]["labels"], {"gpu-health/verdict": "fail"})

    def test_gate_leaves_a_released_node_alone(self):
        os.environ["NODE_NAME"] = "gpu-node-1"
        fake, calls = self.gate_api(tainted=False)
        rc, report = self.run_check({"gpus": [gpu(0, behavior="crash")]}, "--node-gate", api=fake)
        self.assertEqual(rc, 0)
        self.assertIsNone(report)
        self.assertEqual([c[0] for c in calls], ["GET"])
        self.assertTrue(self.termination.startswith("SKIP node gpu-node-1"), self.termination)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "loading-0")))

    def test_gate_needs_the_node_name(self):
        fake, calls = self.gate_api()
        rc, _ = self.run_check({"gpus": [gpu(0)]}, "--node-gate", api=fake)
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

    def test_without_nvidia_smi_the_workload_still_decides(self):
        rc, report = self.run_check({"gpus": [gpu(0)]}, smi=False)
        self.assertEqual(rc, 0)
        self.assertIn("nvidia-smi unavailable", " ".join(report["warnings"]))
        rc, report = self.run_check({"gpus": [gpu(0, faults={"curve": 1})]}, smi=False)
        self.assertEqual(rc, 1)


class NodeGate(unittest.TestCase):
    """gate_node against a fake API server: the calls it makes, not a cluster."""

    def api(self, taints, conflicts=0, get_code=200):
        calls = []
        state = {"conflicts": conflicts, "rv": 7}

        def fake(method, path, body=None, content_type=None):
            calls.append((method, path, body, content_type))
            if method == "GET":
                return get_code, {"metadata": {"name": "n1", "resourceVersion": str(state["rv"])},
                                  "spec": {"taints": list(taints)}}
            if state["conflicts"]:
                state["conflicts"] -= 1
                state["rv"] += 1
                return 409, {"message": "the object has been modified"}
            return 200, {}
        return fake, calls

    PENDING = {"key": "gpu-health/pending", "value": "true", "effect": "NoSchedule"}
    OTHER = {"key": "nvidia.com/gpu", "value": "present", "effect": "NoSchedule"}

    def test_pass_lifts_only_the_gate_taint_and_labels(self):
        fake, calls = self.api([self.PENDING, self.OTHER])
        err = gpu_health.gate_node("n1", "pass", "PASS 8/8", "gpu-health/pending",
                                   "gpu-health/verdict", api=fake)
        self.assertIsNone(err)
        method, path, body, ctype = calls[-1]
        self.assertEqual((method, path, ctype),
                         ("PATCH", "/api/v1/nodes/n1", "application/merge-patch+json"))
        self.assertEqual(body["spec"]["taints"], [self.OTHER])
        self.assertEqual(body["metadata"]["labels"], {"gpu-health/verdict": "pass"})
        self.assertEqual(body["metadata"]["resourceVersion"], "7")
        self.assertIn("PASS 8/8", body["metadata"]["annotations"]["gpu-health/verdict"])

    def test_pass_with_only_the_gate_taint_clears_the_list(self):
        fake, calls = self.api([self.PENDING])
        self.assertIsNone(gpu_health.gate_node("n1", "pass", "PASS", "gpu-health/pending",
                                               "gpu-health/verdict", api=fake))
        self.assertIsNone(calls[-1][2]["spec"]["taints"])

    def test_fail_keeps_the_taint(self):
        fake, calls = self.api([self.PENDING])
        self.assertIsNone(gpu_health.gate_node("n1", "fail", "FAIL", "gpu-health/pending",
                                               "gpu-health/verdict", api=fake))
        body = calls[-1][2]
        self.assertNotIn("spec", body)
        self.assertEqual(body["metadata"]["labels"], {"gpu-health/verdict": "fail"})

    def test_conflict_is_retried_against_the_new_version(self):
        fake, calls = self.api([self.PENDING], conflicts=2)
        self.assertIsNone(gpu_health.gate_node("n1", "pass", "PASS", "gpu-health/pending",
                                               "gpu-health/verdict", api=fake))
        patches = [c for c in calls if c[0] == "PATCH"]
        self.assertEqual([p[2]["metadata"]["resourceVersion"] for p in patches], ["7", "8", "9"])

    def test_errors_are_reported(self):
        fake, _ = self.api([self.PENDING], get_code=403)
        err = gpu_health.gate_node("n1", "pass", "PASS", "gpu-health/pending",
                                   "gpu-health/verdict", api=fake)
        self.assertIn("HTTP 403", err)
        fake, _ = self.api([self.PENDING], conflicts=9)
        err = gpu_health.gate_node("n1", "pass", "PASS", "gpu-health/pending",
                                   "gpu-health/verdict", api=fake)
        self.assertIn("still conflicting", err)


class Pieces(unittest.TestCase):
    def test_parse_value(self):
        p = gpu_health.parse_value
        self.assertEqual(p("[N/A]"), None)
        self.assertEqual(p("[Not Supported]"), None)
        self.assertEqual(p("0x0000000000000044"), 0x44)
        self.assertEqual(p("1410"), 1410)
        self.assertEqual(p("73.00"), 73.0)
        self.assertEqual(p("Enabled"), "Enabled")

    def test_summarize_telemetry(self):
        rows = [{"temperature.gpu": 60, "power.draw": 500.0, "clocks.sm": 1980,
                 "clocks_event_reasons.active": 0x4},
                {"temperature.gpu": 70, "power.draw": 520.0, "clocks.sm": 1950,
                 "clocks_throttle_reasons.active": 0x20}]
        s = gpu_health.summarize_telemetry(rows)
        self.assertEqual(s["temperatureMaxC"], 70)
        self.assertEqual(s["powerMeanW"], 510.0)
        self.assertEqual(s["smClockMinMHz"], 1950)
        self.assertEqual(s["reasons"], ["sw_power_cap", "sw_thermal_slowdown"])

    def test_last_json(self):
        self.assertEqual(gpu_health.last_json('noise\n{"a": 1}\n{"b": 2}\ntrailer'), {"b": 2})
        self.assertIsNone(gpu_health.last_json("no json here"))

    def test_available_cpus_is_positive(self):
        self.assertGreaterEqual(gpu_health.available_cpus(), 1)


if __name__ == "__main__":
    unittest.main()
