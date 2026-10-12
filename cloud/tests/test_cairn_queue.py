"""cloud/cairn_queue.py: the specs and pod variables it sends, the job script
run locally, and, when a cairn binary is at hand (CAIRN_BIN or `cairn` on
PATH), jobs through a real cairn agent and node.  No pod is rented."""
import base64
import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import cairn_queue  # noqa: E402

CAIRN = os.environ.get("CAIRN_BIN") or shutil.which("cairn")


def make_tree(root):
    """A shipped tree, as ship.py leaves it on a runner: the two scripts every job
    runs, a stub toolchain, and some files."""
    (root / "cloud").mkdir(parents=True)
    shutil.copy(HERE / "job_runner.sh", root / "cloud" / "job_runner.sh")
    shutil.copy(HERE / "install_tree.py", root / "cloud" / "install_tree.py")
    (root / "cloud" / "pod_env.sh").write_text("export POD_ENV_SOURCED=yes\n")
    (root / "suite").mkdir()
    (root / "suite" / "Cargo.toml").write_text("[package]\n")
    (root / "notes.txt").write_text("from the tree\n")
    return root


class SpecTest(unittest.TestCase):
    def test_a_job_runs_unconfined_on_its_tree_and_says_why_it_asks_for_no_gpu(self):
        spec = cairn_queue.job_spec("20261006-120000-abcd", "k" * 20, "nvidia-smi",
                                    outs=["results/a.json", "logs"], timeout=600,
                                    git={"commit": "c0ffee", "branch": "b", "dirty": True})
        self.assertEqual((spec["sandbox"], spec["rootfs"], spec["gpus"]), ("none", "/", 0))
        self.assertEqual(spec["argv"], ["bash", "-c", cairn_queue.JOB_SCRIPT])
        self.assertEqual(spec["inputs"], [{"source": f"/root/runner/trees/{'k' * 20}",
                                           "target": "/in/tree"}])
        self.assertEqual(spec["env"]["JOB_CMD"], "nvidia-smi")
        self.assertEqual(spec["env"]["JOB_OUTS"], "results/a.json\nlogs")
        self.assertEqual((spec["env"]["JOB_COMMIT"], spec["env"]["JOB_DIRTY"]), ("c0ffee", "1"))
        self.assertEqual(spec["timeout_seconds"], 600)
        self.assertTrue(spec["network"])
        self.assertIn("GPU", spec["note"])
        self.assertNotIn("objective_id", spec)

    def test_an_objective_and_task_are_passed_for_the_lease(self):
        spec = cairn_queue.job_spec("j", "k", "true", objective="sha256:o", task="unit:7")
        self.assertEqual((spec["objective_id"], spec["task"]), ("sha256:o", "unit:7"))

    def test_the_job_reads_its_tree_where_cairn_exports_the_input(self):
        # cairn names an unconfined job's input CAIRN_LAB_MOUNT_<TARGET>.
        self.assertIn('install_tree.py" "$CAIRN_LAB_MOUNT_IN_TREE" "$work"', cairn_queue.JOB_SCRIPT)
        self.assertIn("JOB_DIR=$CAIRN_LAB_OUT", cairn_queue.JOB_SCRIPT)

    def test_a_runner_is_a_pod_whose_boot_script_is_the_runner(self):
        args = cairn_queue.parse(["up", "gpu-1"])
        env = cairn_queue.runner_env(args)
        self.assertEqual(base64.b64decode(env["POD_BOOT_B64"]),
                         (HERE / "cairn_runner.sh").read_bytes())
        self.assertEqual(env["CAIRN_RUNNER_NAME"], "gpu-1")
        self.assertEqual(env["CAIRN_VERSION"], cairn_queue.CAIRN_VERSION)
        self.assertEqual(env["RUNNER_IDLE_MINUTES"], "60")
        self.assertNotIn("CAIRN_AGENT_NODES", env)
        args = cairn_queue.parse(["up", "gpu-1", "--node", "http://10.0.0.2:8080",
                                  "--node", "http://10.0.0.3:8080", "--idle-minutes", "0"])
        env = cairn_queue.runner_env(args)
        self.assertEqual(env["CAIRN_AGENT_NODES"], "http://10.0.0.2:8080,http://10.0.0.3:8080")
        self.assertEqual(env["RUNNER_IDLE_MINUTES"], "0")

    def test_runners_default_to_a_gpu_and_a_day(self):
        args = cairn_queue.parse(["up", "gpu-1"])
        self.assertEqual((args.max_hours, args.cpu, args.gpu), (24.0, 0, []))


class ParseTest(unittest.TestCase):
    def test_submit_keeps_the_command_after_the_separator(self):
        args = cairn_queue.parse(["submit", "gpu-1", "--out", "a.json", "--only", "suite", "--",
                                  "cd", "suite", "&&", "cargo", "test"])
        self.assertEqual(args.command, ["cd", "suite", "&&", "cargo", "test"])
        self.assertEqual((args.out, args.only), (["a.json"], ["suite"]))
        self.assertEqual(args.timeout, cairn_queue.DEFAULT_TIMEOUT)

    def test_an_objective_needs_a_task(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cairn_queue.parse(["submit", "gpu-1", "--objective", "sha256:o", "--", "true"])


class TreeTest(unittest.TestCase):
    def test_a_subset_still_carries_the_job_scripts(self):
        files = cairn_queue.tree_files(cairn_queue.REPO, ["suite/src/cli"])
        self.assertTrue(set(cairn_queue.JOB_SCRIPTS) <= set(files))
        self.assertTrue(all(f in cairn_queue.JOB_SCRIPTS or f.startswith("suite/src/cli/")
                            for f in files))

    def test_an_edit_makes_a_new_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_text("1")
            before = cairn_queue.tree_key(root, ["a.txt"])
            self.assertEqual(before, cairn_queue.tree_key(root, ["a.txt"]))
            os.utime(root / "a.txt", ns=(1, 2))
            self.assertNotEqual(before, cairn_queue.tree_key(root, ["a.txt"]))


class StateTest(unittest.TestCase):
    def test_each_place_a_job_can_be(self):
        listing = {"queued": ["q"], "running": ["r"],
                   "done": [{"id": "d", "receipt": {"succeeded": True}},
                            {"id": "x.duplicate", "receipt": None}]}
        state = cairn_queue.job_state
        self.assertEqual(state(listing, "q"), ("queued", None))
        self.assertEqual(state(listing, "r"), ("running", None))
        self.assertEqual(state(listing, "d"), ("done", {"succeeded": True}))
        self.assertEqual(state(listing, "x"), ("refused", None))
        self.assertEqual(state(listing, "y"), ("unknown", None))


class JobScriptTest(unittest.TestCase):
    """JOB_SCRIPT as cairn runs it unconfined: the input and out/ are host paths in the env."""

    def test_the_job_replaces_the_checkout_but_keeps_the_build_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = make_tree(tmp / "tree")
            work, out = tmp / "checkout", tmp / "out"
            (work / "suite" / "target").mkdir(parents=True)
            (work / "suite" / "target" / "kept.o").write_text("warm")
            (work / "stale.txt").write_text("from the last job")
            out.mkdir()
            command = ("mkdir -p results && echo $POD_ENV_SOURCED > results/a.txt && "
                       "ls suite/target && cat notes.txt && test ! -e stale.txt")
            env = {**os.environ, "RUNNER_CHECKOUT": str(work), "CAIRN_LAB_OUT": str(out),
                   "CAIRN_LAB_MOUNT_IN_TREE": str(src), "JOB_ID": "j1",
                   "JOB_CMD": command, "JOB_OUTS": "results", "JOB_CHANGED": "0"}
            proc = subprocess.run(["bash", "-c", cairn_queue.JOB_SCRIPT], env=env,
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("kept.o", proc.stdout)
            self.assertIn("from the tree", proc.stdout)
            with tarfile.open(out / "out.tar.gz") as tar:
                self.assertEqual(tar.extractfile("results/a.txt").read(), b"yes\n")
            self.assertEqual(json.loads((out / "status.json").read_text())["returncode"], 0)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(CAIRN, "no cairn binary (set CAIRN_BIN)")
class CairnAgentTest(unittest.TestCase):
    """Two jobs through `cairn agent submit` and `cairn agent run`, registered with a
    private node, the way cairn_runner.sh runs them on a pod."""

    def test_jobs_run_one_at_a_time_to_receipts_and_the_node_lists_the_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            http, p2p = free_port(), free_port()
            node_env = {**os.environ, "CAIRN_DATA": str(tmp / "node"), "CAIRN_SEEDS": "off",
                        "CAIRN_BEACON_PORT": "off", "CAIRN_PORTMAP": "off"}
            node = subprocess.Popen([CAIRN, "run", "--no-mcp", "--listen", f"127.0.0.1:{p2p}",
                                     "--serve", f"127.0.0.1:{http}"], env=node_env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                url = f"http://127.0.0.1:{http}"
                for _ in range(60):
                    try:
                        urllib.request.urlopen(f"{url}/hosts", timeout=2).read()
                        break
                    except OSError:
                        time.sleep(0.5)
                src = make_tree(tmp / "tree")
                spool = tmp / "agent"
                for job_id in ("first", "second"):
                    spec = cairn_queue.job_spec(job_id, "k", f"sleep 1; echo {job_id} > out.txt",
                                                outs=["out.txt"], timeout=120)
                    spec["inputs"][0]["source"] = str(src)
                    path = tmp / f"{job_id}.json"
                    path.write_text(json.dumps(spec))
                    subprocess.run([CAIRN, "agent", "submit", str(path), "--data-dir", str(spool)],
                                   check=True, capture_output=True)
                agent_env = {**os.environ, "RUNNER_CHECKOUT": str(tmp / "checkout")}
                run = subprocess.run([CAIRN, "agent", "run", "--once", "--node", url,
                                      "--name", "runner-test", "--sandbox", "none",
                                      "--data-dir", str(spool)], env=agent_env,
                                     capture_output=True, text=True, timeout=300, check=False)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                listing = json.loads(subprocess.run(
                    [CAIRN, "agent", "jobs", "--data-dir", str(spool), "--json"],
                    check=True, capture_output=True).stdout)
                receipts = {e["id"]: e["receipt"] for e in listing["done"]}
                self.assertEqual(set(receipts), {"first", "second"})
                for job_id, receipt in receipts.items():
                    self.assertEqual(cairn_queue.job_state(listing, job_id)[0], "done")
                    self.assertTrue(receipt["succeeded"], receipt)
                    self.assertEqual(receipt["sandbox"], "none")
                    with tarfile.open(spool / "jobs" / "done" / job_id / "out" / "out.tar.gz") as tar:
                        self.assertEqual(tar.extractfile("out.txt").read().decode(), f"{job_id}\n")
                self.assertLessEqual(receipts["first"]["finished"], receipts["second"]["started"])
                roster = json.loads(urllib.request.urlopen(f"{url}/hosts", timeout=5).read())
                host = next(h for h in roster["hosts"] if h["host"] == "runner-test")
                self.assertEqual((host["jobs"]["completed"], host["jobs"]["capacity"]), (2, 1))
            finally:
                node.terminate()
                node.wait(timeout=30)


if __name__ == "__main__":
    unittest.main()
