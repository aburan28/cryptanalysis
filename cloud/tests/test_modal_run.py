import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import modal_run  # noqa: E402


class CommandLineTest(unittest.TestCase):
    def run_main(self, argv, command="cmd_run"):
        calls = []
        with mock.patch.object(modal_run, command, side_effect=lambda a: calls.append(a) or 0):
            self.assertEqual(modal_run.main(argv), 0)
        return calls[0]

    def test_options_then_command(self):
        args = self.run_main(["run", "--image", "cuda", "--gpu", "H100", "--shards", "4",
                              "--out", "results", "--", "python3", "run.py", "--seed", "1"])
        self.assertEqual((args.image, args.gpu, args.shards), ("cuda", "H100", 4))
        self.assertEqual(args.command, ["python3", "run.py", "--seed", "1"])

    def test_run_needs_a_command(self):
        with self.assertRaises(SystemExit):
            modal_run.main(["run", "--image", "cpu"])

    def test_other_subcommands_take_no_command(self):
        with self.assertRaises(SystemExit):
            modal_run.main(["status", "j1", "--", "ls"])
        self.assertEqual(self.run_main(["status", "j1"], "cmd_status").job, "j1")


class JobTest(unittest.TestCase):
    def test_shard_environment(self):
        env = modal_run.shard_env("j1", 2, 4, "make test", ["a", "b"], True, {"SEED": "7"})
        self.assertEqual(env["JOB_DIR"], "/jobs/j1/shards/2")
        self.assertEqual(env["JOB_SRC"], "/jobs/j1/src.tar.gz")
        self.assertEqual((env["SHARD_INDEX"], env["SHARD_COUNT"]), ("2", "4"))
        self.assertEqual(env["JOB_OUTS"], "a\nb")
        self.assertEqual((env["JOB_CHANGED"], env["SEED"]), ("1", "7"))

    def test_extra_env_cannot_override_the_job_contract(self):
        env = modal_run.shard_env("j1", 0, 1, "true", [], False, {"JOB_DIR": "/elsewhere"})
        self.assertEqual(env["JOB_DIR"], "/jobs/j1/shards/0")

    def test_parse_env(self):
        self.assertEqual(modal_run.parse_env(["A=1", "B=x=y"]), {"A": "1", "B": "x=y"})
        with self.assertRaises(SystemExit):
            modal_run.parse_env(["novalue"])

    def test_exit_code_is_the_first_failure(self):
        ok = {"returncode": 0}
        self.assertEqual(modal_run.exit_code({0: ok, 1: ok}, {}), 0)
        self.assertEqual(modal_run.exit_code({0: ok, 1: {"returncode": 2}}, {}), 2)
        self.assertEqual(modal_run.exit_code({0: None}, {0: 137}), 137)
        self.assertEqual(modal_run.exit_code({0: None}, {0: None}), 1)

    def test_job_ids_sort_by_creation_time(self):
        first = modal_run.new_job_id()
        self.assertRegex(first, r"^\d{8}-\d{6}-[0-9a-f]{4}$")


if __name__ == "__main__":
    unittest.main()
