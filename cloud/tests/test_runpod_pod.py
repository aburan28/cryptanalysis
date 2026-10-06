"""The pod requests cloud/runpod_pod.py would send; no service is called."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runpod_pod  # noqa: E402

KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItest test"


class PodBodyTest(unittest.TestCase):
    def test_gpu_pod_takes_the_default_gpus_and_a_vcpu_floor(self):
        args = runpod_pod.parse(["run", "ic", "--", "nvidia-smi"])
        body = runpod_pod.pod_body(args, KEY)
        self.assertEqual(body["computeType"], "GPU")
        self.assertEqual(body["gpuTypeIds"], runpod_pod.DEFAULT_GPUS)
        self.assertEqual(body["gpuTypePriority"], "custom")
        self.assertEqual(body["minVCPUPerGPU"], 16)
        self.assertNotIn("vcpuCount", body)
        self.assertEqual(body["ports"], ["22/tcp"])
        self.assertEqual(body["env"]["PUBLIC_KEY"], KEY)
        self.assertEqual(body["env"]["F4_MAX_SECONDS"], str(6 * 3600))

    def test_named_gpus_keep_their_order(self):
        args = runpod_pod.parse(["up", "ic", "--gpu", "NVIDIA GeForce RTX 4090",
                                 "--gpu", "NVIDIA GeForce RTX 5090", "--max-hours", "1.5"])
        body = runpod_pod.pod_body(args, KEY)
        self.assertEqual(body["gpuTypeIds"], ["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090"])
        self.assertEqual(body["env"]["F4_MAX_SECONDS"], "5400")

    def test_cpu_pod(self):
        args = runpod_pod.parse(["up", "cpu", "--cpu", "32"])
        body = runpod_pod.pod_body(args, KEY)
        self.assertEqual(body["computeType"], "CPU")
        self.assertEqual(body["vcpuCount"], 32)
        self.assertEqual(body["cpuFlavorIds"], ["cpu5c", "cpu3c"])
        self.assertNotIn("gpuTypeIds", body)

    def test_cpu_and_gpu_are_exclusive(self):
        with self.assertRaises(SystemExit):
            runpod_pod.parse(["up", "x", "--cpu", "8", "--gpu", "NVIDIA GeForce RTX 5090"])

    def test_run_keeps_the_command_and_outputs(self):
        args = runpod_pod.parse(["run", "ic", "--out", "a/b.json", "--keep", "--",
                                 "cd", "suite", "&&", "cargo", "build"])
        self.assertEqual(args.command, ["cd", "suite", "&&", "cargo", "build"])
        self.assertEqual(args.out, ["a/b.json"])
        self.assertTrue(args.keep)

    def test_pid1_hands_over_to_the_image_start_script(self):
        self.assertIn("podStop", runpod_pod.STAGE0)
        self.assertTrue(runpod_pod.STAGE0.rstrip().endswith("exec sleep infinity"))
        self.assertIn("exec /start.sh", runpod_pod.STAGE0)

    def test_bootstrap_ends_in_the_checkout(self):
        self.assertTrue(runpod_pod.BOOTSTRAP.rstrip().endswith(f"cd {runpod_pod.REMOTE}"))
        self.assertIn("CA_NVRTC_LIB", runpod_pod.BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
