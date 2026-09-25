import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fleet  # noqa: E402

FLEET = fleet.load_fleet()


def body_for(name, **kwargs):
    spec = FLEET["workers"][name]
    env = fleet.pod_env(name, spec, FLEET, cursor_key="crsr_test", **kwargs)
    return fleet.pod_body(name, spec, FLEET, env)


class PodBodyTest(unittest.TestCase):
    def test_every_worker_has_a_complete_spec(self):
        for name, spec in FLEET["workers"].items():
            for key in ("computeType", "imageName", "containerDiskInGb", "volumeInGb", "features",
                        "idleStopMinutes", "description"):
                self.assertIn(key, spec, f"{name} lacks {key}")

    def test_cpu_pod(self):
        body = body_for("rp-cpu-1")
        self.assertEqual(body["computeType"], "CPU")
        self.assertEqual(body["vcpuCount"], 32)
        self.assertIn("cpu5c", body["cpuFlavorIds"])
        self.assertNotIn("gpuTypeIds", body)

    def test_gpu_pod(self):
        body = body_for("rp-gpu-1")
        self.assertEqual(body["computeType"], "GPU")
        self.assertTrue(body["gpuTypeIds"])
        self.assertEqual(body["gpuTypePriority"], "custom")
        self.assertNotIn("vcpuCount", body)

    def test_boot_contract(self):
        body = body_for("rp-gpu-1", public_keys="ssh-ed25519 AAAA test")
        self.assertEqual(body["dockerEntrypoint"], ["bash", "-c"])
        self.assertEqual(body["dockerStartCmd"], [fleet.STAGE0])
        self.assertEqual(body["ports"], ["22/tcp"])
        env = body["env"]
        self.assertEqual(env["FLEET_WORKER_NAME"], "rp-gpu-1")
        self.assertEqual(env["FLEET_REF"], FLEET["fleetRef"])
        self.assertEqual(env["FLEET_FEATURES"], "msolve,cuda13")
        self.assertIn("kind=gpu", env["FLEET_LABELS"])
        self.assertEqual(env["CURSOR_API_KEY"], "crsr_test")
        self.assertEqual(env["PUBLIC_KEY"], "ssh-ed25519 AAAA test")
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(body_for("rp-cpu-1", github_token="ghp_x")["env"]["GITHUB_TOKEN"], "ghp_x")

    def test_ref_override(self):
        self.assertEqual(body_for("rp-cpu-1", ref="my-branch")["env"]["FLEET_REF"], "my-branch")

    def test_stage0_is_valid_bash(self):
        subprocess.run(["bash", "-n", "-c", fleet.STAGE0], check=True)

    def test_boot_reads_every_variable_the_pod_is_given(self):
        boot = (fleet.HERE / "worker" / "boot.sh").read_text()
        for key in body_for("rp-cpu-1", github_token="g")["env"]:
            if key.startswith("FLEET_"):
                self.assertIn(key, boot, f"boot.sh ignores {key}")


class PodLookupTest(unittest.TestCase):
    def test_find_pod_prefers_a_running_pod_and_ignores_terminated_ones(self):
        pods = [{"id": "a", "name": "rp-cpu-1", "desiredStatus": "EXITED"},
                {"id": "b", "name": "rp-cpu-1", "desiredStatus": "RUNNING"},
                {"id": "c", "name": "rp-cpu-1", "desiredStatus": "TERMINATED"},
                {"id": "d", "name": "other", "desiredStatus": "RUNNING"}]
        self.assertEqual(fleet.find_pod("rp-cpu-1", pods)["id"], "b")
        self.assertEqual(fleet.find_pod("rp-cpu-1", pods[:1] + pods[2:])["id"], "a")
        self.assertIsNone(fleet.find_pod("rp-gpu-1", pods))

    def test_ssh_endpoint(self):
        self.assertEqual(fleet.ssh_endpoint({"publicIp": "1.2.3.4", "portMappings": {"22": 10341}}),
                         ("1.2.3.4", 10341))
        self.assertIsNone(fleet.ssh_endpoint({"publicIp": None, "portMappings": None}))


class CommandLineTest(unittest.TestCase):
    def run_main(self, argv, command):
        calls = []
        with mock.patch.object(fleet, command, side_effect=lambda a: calls.append(a) or 0):
            self.assertEqual(fleet.main(argv), 0)
        return calls[0]

    def test_run_takes_options_before_the_double_dash(self):
        args = self.run_main(["run", "rp-cpu-1", "--out", "results", "--changed", "--",
                              "make", "-j32", "test"], "cmd_run")
        self.assertEqual((args.name, args.out, args.changed), ("rp-cpu-1", ["results"], True))
        self.assertEqual(args.command, ["make", "-j32", "test"])

    def test_run_without_a_command_is_an_error(self):
        with self.assertRaises(SystemExit):
            fleet.main(["run", "rp-cpu-1"])

    def test_ssh_passes_the_command_through(self):
        args = self.run_main(["ssh", "rp-gpu-1", "ls", "-la"], "cmd_ssh")
        self.assertEqual(args.command, ["ls", "-la"])


class SshKeyTest(unittest.TestCase):
    def test_pkcs8_keys_are_converted_for_openssh(self):
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.skipTest("cryptography is not installed")
        pem = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        converted = fleet.openssh_private_key(pem)
        self.assertTrue(converted.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"))
        self.assertEqual(fleet.openssh_private_key(converted), converted)


if __name__ == "__main__":
    unittest.main()
