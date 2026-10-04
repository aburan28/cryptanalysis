"""cloud/taskq: the ECDLP job wrapper, its certificates, and the example specs.

The solver output under cloud/taskq/testdata/ was captured from a real
`ca solve` build (see cloud/taskq/README.md, "Test data"). A stand-in `ca`
replays it, so these tests need no C build; set CA_BIN to a built `ca` to also
run the wrapper against the real solver.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TASKQ_DIR = HERE / "taskq"
REPO = HERE.parent
DATA = TASKQ_DIR / "testdata"
sys.path.insert(0, str(TASKQ_DIR))
import ca_ecdlp_job as job  # noqa: E402

try:
    from taskq import protocol as taskq_protocol
except ImportError:  # taskq is installed in CI when the git URL is reachable
    taskq_protocol = None
try:
    from taskq import verify as taskq_verify
except ImportError:
    taskq_verify = None


# -- an independent recompute, so a certificate is checked even without taskq --

def _add(P, Q, a, p):
    if P is None:
        return Q
    if Q is None:
        return P
    (x1, y1), (x2, y2) = P, Q
    if x1 == x2 and (y1 + y2) % p == 0:
        return None
    if P == Q:
        lam = (3 * x1 * x1 + a) * pow(2 * y1, -1, p) % p
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (lam * lam - x1 - x2) % p
    return x3, (lam * (x1 - x3) - y1) % p


def _mul(k, P, a, p):
    R = None
    while k:
        if k & 1:
            R = _add(R, P, a, p)
        P = _add(P, P, a, p)
        k >>= 1
    return R


def check_certificate(cert):
    c, st = cert["curve"], cert["statement"]
    p, a, b = (job.to_int(c[f]) for f in ("p", "a", "b"))
    P = tuple(job.to_int(v) for v in st["P"])
    Q = tuple(job.to_int(v) for v in st["Q"])
    for x, y in (P, Q):
        assert (y * y - x ** 3 - a * x - b) % p == 0, "point not on curve"
    assert _mul(job.to_int(st["n"]), P, a, p) is None, "n*P != O"
    return _mul(job.to_int(st["k"]), P, a, p) == Q


# -- helpers -----------------------------------------------------------------

def fake_ca(tmp, stdout_file, stderr_file=None, code=0):
    """A stand-in `ca` that replays captured output and records its argv."""
    path = Path(tmp, "ca")
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"open({str(Path(tmp, 'argv.json'))!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        f"sys.stdout.write(open({str(DATA / stdout_file)!r}).read())\n"
        + (f"sys.stderr.write(open({str(DATA / stderr_file)!r}).read())\n" if stderr_file else "")
        + f"sys.exit({code})\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def run_wrapper(tmp, ca, *args, env=None):
    out = Path(tmp, "out")
    old = dict(os.environ)
    os.environ.update(env or {})
    try:
        rc = job.main(["--ca", str(ca), "--out", str(out), *args])
    finally:
        os.environ.clear()
        os.environ.update(old)
    cert = json.loads((out / "certificate.json").read_text())
    metrics = json.loads((out / "metrics.json").read_text())
    return rc, cert, metrics, out


INSTANCE_26 = str(TASKQ_DIR / "instances" / "generic-26.json")
INSTANCE_48 = str(TASKQ_DIR / "instances" / "p48-b111.json")


class ParseSolverOutput(unittest.TestCase):
    def test_solved_outputs(self):
        cases = {"rho-generic-26-seed1.stdout": 1234567,
                 "rho-p48-b111-seed1.stdout": 86811570583973,
                 "gpu-rho-emulate-generic-26-seed1.stdout": 1234567,
                 "gpu-rho-emulate-p48-b111-seed1.stdout": 86811570583973}
        for name, k in cases.items():
            with self.subTest(name):
                report = job.parse_solver_stdout((DATA / name).read_text())
                self.assertEqual(report["status"], "ok")
                self.assertEqual(job.solved_scalar(report), k)
                for f in job.STAT_FIELDS:
                    self.assertIn(f, report)

    def test_unsolved_outputs(self):
        for name, status in (("rho-p48-b111-maxops100000.stdout", "limit reached"),
                             ("gpu-rho-cuda-not-compiled.stdout", "unsupported")):
            with self.subTest(name):
                report = job.parse_solver_stdout((DATA / name).read_text())
                self.assertEqual(report["status"], status)
                self.assertIsNone(job.solved_scalar(report))

    def test_no_status_line(self):
        self.assertIsNone(job.parse_solver_stdout(""))
        self.assertIsNone(job.parse_solver_stdout("error: element is not in the group\n"))
        self.assertIsNone(job.solved_scalar(None))

    def test_integer_encodings(self):
        self.assertEqual(job.to_int("0x10"), 16)
        self.assertEqual(job.to_int("16"), 16)
        self.assertEqual(job.to_int(16), 16)
        self.assertEqual(job.parse_point("0x10,17"), (16, 17))
        self.assertEqual(job.parse_point(["0x10", 17]), (16, 17))
        with self.assertRaises(ValueError):
            job.to_int(True)


class Wrapper(unittest.TestCase):
    def test_solve_writes_discrete_log_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-generic-26-seed1.stdout")
            rc, cert, m, out = run_wrapper(tmp, ca, "--instance", INSTANCE_26, "--seed", "1")
            argv = json.loads(Path(tmp, "argv.json").read_text())
        self.assertEqual(rc, 0)
        self.assertEqual(argv, ["solve", "--alg", "rho", "--group", "ec", "--p", "67108879",
                                "--a", "2", "--b", "3", "--order", "3355777",
                                "--g", "49721874,20362961", "--h", "32219285,61861565",
                                "--seed", "1"])
        self.assertEqual(cert, {
            "kind": "discrete_log",
            "curve": {"field": "prime", "p": "67108879", "a": "2", "b": "3"},
            "statement": {"P": ["49721874", "20362961"], "Q": ["32219285", "61861565"],
                          "k": "1234567", "n": "3355777"}})
        self.assertTrue(check_certificate(cert))
        self.assertEqual((m["solved"], m["k"], m["solver_status"]), (True, "1234567", "ok"))
        self.assertEqual((m["ops"], m["iterations"], m["table_entries"], m["collisions"]),
                         (2869, 90, 85, 4))
        self.assertEqual(m["solver_seconds"], 0.000421)
        self.assertEqual(m["instance"]["order_bits"], 22)
        self.assertAlmostEqual(m["ops_per_sqrt_order"], 2869 / 3355777 ** 0.5)

    def test_gpu_rho_keeps_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "gpu-rho-emulate-p48-b111-seed1.stdout")
            rc, cert, m, _ = run_wrapper(tmp, ca, "--instance", INSTANCE_48, "--alg", "gpu-rho",
                                         "--seed", "1", "--", "--backend", "emulate")
            argv = json.loads(Path(tmp, "argv.json").read_text())
        self.assertEqual(rc, 0)
        self.assertEqual(argv[-2:], ["--backend", "emulate"])
        self.assertEqual((m["launches"], m["threads"], m["ops"]), (23, 512, 21434500))
        self.assertEqual(cert["statement"]["k"], "86811570583973")
        self.assertTrue(check_certificate(cert))

    def test_limit_reached_claims_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-p48-b111-maxops100000.stdout", code=1)
            rc, cert, m, out = run_wrapper(tmp, ca, "--instance", INSTANCE_48,
                                           "--max-ops", "100000")
        self.assertEqual(rc, 1)
        self.assertEqual(cert, {"kind": "none"})
        self.assertEqual((m["solved"], m["k"], m["solver_status"]),
                         (False, None, "limit reached"))
        self.assertEqual(m["ops"], 244765)

    def test_unparseable_success_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-bad-point.stderr", code=0)  # no JSON on stdout
            rc, cert, m, _ = run_wrapper(tmp, ca, "--instance", INSTANCE_26)
        self.assertEqual(rc, 3)
        self.assertEqual(cert, {"kind": "none"})
        self.assertIsNotNone(m["parse_error"])

    def test_usage_error_passes_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp, "empty")
            empty.write_text("")
            ca = fake_ca(tmp, "rho-generic-26-seed1.stdout")
            # replace the replayed stdout with nothing and exit 2, as ca does
            ca.write_text(ca.read_text().replace(str(DATA / "rho-generic-26-seed1.stdout"),
                                                 str(empty)).replace("sys.exit(0)", "sys.exit(2)"))
            rc, cert, m, _ = run_wrapper(tmp, ca, "--instance", INSTANCE_26)
        self.assertEqual(rc, 2)
        self.assertEqual(cert, {"kind": "none"})

    def test_seed_from_repetition(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-generic-26-seed1.stdout")
            _, _, m, _ = run_wrapper(tmp, ca, "--instance", INSTANCE_26, "--seed", "10",
                                     "--seed-from-repetition", env={"TASKQ_REPETITION": "3"})
            argv = json.loads(Path(tmp, "argv.json").read_text())
        self.assertEqual(m["seed"], 13)
        self.assertEqual(argv[argv.index("--seed") + 1], "13")

    def test_instance_on_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-generic-26-seed1.stdout")
            rc, cert, _, _ = run_wrapper(tmp, ca, "--p", "67108879", "--a", "2", "--b", "3",
                                         "--order", "0x333481", "--P", "49721874,20362961",
                                         "--Q", "32219285,61861565")
        self.assertEqual(rc, 0)
        self.assertEqual(cert["statement"]["n"], "3355777")
        self.assertTrue(check_certificate(cert))

    @unittest.skipUnless(taskq_verify, "taskq.verify is not installed")
    def test_taskq_verifier_accepts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ca = fake_ca(tmp, "rho-p48-b111-seed1.stdout")
            _, cert, _, _ = run_wrapper(tmp, ca, "--instance", INSTANCE_48)
        self.assertEqual(taskq_verify.verify_certificate(cert)["status"], "verified")
        self.assertEqual(taskq_verify.verify_certificate({"kind": "none"})["status"], "no_claim")

    @unittest.skipUnless(os.environ.get("CA_BIN"), "set CA_BIN to a built ca to run the solver")
    def test_real_solver(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, cert, m, _ = run_wrapper(tmp, os.environ["CA_BIN"], "--instance", INSTANCE_26,
                                         "--seed", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(cert["statement"]["k"], "1234567")
        self.assertTrue(check_certificate(cert))


class Instances(unittest.TestCase):
    def test_points_on_curve_with_order_n(self):
        for path in sorted((TASKQ_DIR / "instances").glob("*.json")):
            with self.subTest(path.name):
                doc = json.loads(path.read_text())
                c = doc["curve"]
                p, a, b, n = c["p"], c["a"], c["b"], doc["order"]
                for x, y in (doc["P"], doc["Q"]):
                    self.assertEqual((y * y - x ** 3 - a * x - b) % p, 0)
                self.assertIsNone(_mul(n, tuple(doc["P"]), a, p))
                self.assertIsNone(_mul(n, tuple(doc["Q"]), a, p))


class ExampleSpecs(unittest.TestCase):
    def specs(self):
        return sorted((TASKQ_DIR / "examples").glob("*.json"))

    def test_examples_reference_files_that_exist(self):
        for path in self.specs():
            with self.subTest(path.name):
                spec = json.loads(path.read_text())
                self.assertEqual(spec["source"]["repo"], "cryptanalysis")
                self.assertIn(spec["queue"], ("ca-cpu", "ca-gpu-sm120"))
                argv = spec["command"]["argv"]
                self.assertTrue((REPO / argv[1]).is_file(), argv[1])
                self.assertTrue((REPO / argv[argv.index("--instance") + 1]).is_file())
                self.assertEqual(spec.get("verify"), {"builtin": "certificate"})
                for sp in spec["source"]["sparse_paths"]:
                    self.assertTrue((REPO / sp).is_dir(), sp)

    @unittest.skipUnless(taskq_protocol, "taskq is not installed")
    def test_examples_validate_against_taskq_schema(self):
        knows_verify = "verify" in taskq_protocol.SPEC_SCHEMA["properties"]
        for path in self.specs():
            with self.subTest(path.name):
                spec = json.loads(path.read_text())
                if not knows_verify:
                    # taskq before certificate verification: the rest must still validate.
                    spec.pop("verify")
                taskq_protocol.normalize_spec(spec)


class CliScript(unittest.TestCase):
    def test_runs_as_a_script(self):
        proc = subprocess.run([sys.executable, str(TASKQ_DIR / "ca_ecdlp_job.py"), "--help"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--instance", proc.stdout)


if __name__ == "__main__":
    unittest.main()
