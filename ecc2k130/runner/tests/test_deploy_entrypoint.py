"""Tests for the GPU-aware container entrypoint without a real GPU."""
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "deploy" / "entrypoint.sh"


def run_entrypoint(**values):
    env = os.environ.copy()
    env.update({key: str(value) for key, value in values.items()})
    env["ECC_CLIENT"] = "/bin/true"
    return subprocess.run(
        [str(ENTRYPOINT), "/bin/true"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


class EntrypointTests(unittest.TestCase):
    def test_uses_explicit_capability_override(self):
        result = run_entrypoint(ECC_GPU_ARCH="8.9", ECC_GPU="3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("compute capability 8.9, sm_89", result.stderr)
        self.assertIn("GPU 3", result.stderr)

    def test_maps_blackwell_driver_capability_to_sm_100(self):
        result = run_entrypoint(ECC_GPU_ARCH="10.3")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("compute capability 10.3, sm_100", result.stderr)

    def test_rejects_unsupported_capability(self):
        result = run_entrypoint(ECC_GPU_ARCH="7.5")
        self.assertEqual(result.returncode, 3)
        self.assertIn("unsupported GPU", result.stderr)
        self.assertIn("sm_75", result.stderr)

    def test_rejects_malformed_capability(self):
        result = run_entrypoint(ECC_GPU_ARCH="unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not read a valid compute capability", result.stderr)


if __name__ == "__main__":
    unittest.main()
