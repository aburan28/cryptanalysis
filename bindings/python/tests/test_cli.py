"""Tests for ``python -m cryptanalysis``.

The CLI is tested through ``main()`` rather than by spawning a subprocess: the
subprocess would have to rediscover the shared library, and a failure there
would look like a CLI bug. Calling ``main()`` in-process keeps the two concerns
separate — ``test_bindings.py`` covers loading.

Run with:  cd bindings/python && python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cryptanalysis as ca
from cryptanalysis.__main__ import main

ZP_P = 1000003
ZP_ORDER = 1000002
EC_P, EC_A, EC_B = 1000003, 1, 7


def run(*argv: str) -> tuple[int, dict]:
    """Run one command, returning its exit status and parsed JSON."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(list(argv))
    text = buf.getvalue().strip()
    return rc, json.loads(text) if text else {}


class VersionTests(unittest.TestCase):
    def test_version_reports_the_library_it_loaded(self):
        rc, out = run("version")
        self.assertEqual(rc, 0)
        self.assertEqual(out["version"], ca.version())
        self.assertTrue(out["library"])


class NumberTheoryTests(unittest.TestCase):
    def test_prime(self):
        rc, out = run("prime", "1000003")
        self.assertEqual((rc, out["is_prime"]), (0, True))
        self.assertEqual(out["next_prime"], 1000033)
        _, out = run("prime", "1000001")
        self.assertFalse(out["is_prime"])

    def test_factor_matches_the_known_factorisation(self):
        # 2^32 - 1 = 3 * 5 * 17 * 257 * 65537.
        rc, out = run("factor", "4294967295")
        self.assertEqual(rc, 0)
        self.assertEqual(out["factors"], [[3, 1], [5, 1], [17, 1], [257, 1], [65537, 1]])

    def test_powmod(self):
        rc, out = run("powmod", "--base", "3", "--exp", "100", "--mod", "1000003")
        self.assertEqual((rc, out["result"]), (0, "189751"))

    def test_invmod_reports_non_invertibility_with_exit_1(self):
        rc, out = run("invmod", "--a", "2", "--mod", "1000003")
        self.assertEqual(rc, 0)
        self.assertEqual((2 * int(out["result"])) % 1000003, 1)
        rc, out = run("invmod", "--a", "6", "--mod", "9")
        self.assertEqual((rc, out["invertible"]), (1, False))

    def test_primitive_root_has_full_order(self):
        rc, out = run("primitive-root", "--p", str(ZP_P))
        self.assertEqual(rc, 0)
        with ca.Group.zp(ZP_P, ZP_ORDER) as g:
            self.assertEqual(g.elem_order(int(out["generator"])), ZP_ORDER)

    def test_cheon_divisor(self):
        rc, out = run("cheon-divisor", "--p", str(ZP_P))
        self.assertEqual(rc, 0)
        self.assertEqual((ZP_P - 1) % int(out["divisor"]), 0)


class GroupTests(unittest.TestCase):
    ZP = ("--p", str(ZP_P), "--order", str(ZP_ORDER))
    EC = ("--group", "ec", "--p", str(EC_P), "--a", str(EC_A), "--b", str(EC_B))

    def test_info(self):
        rc, out = run("group", "info", *self.ZP)
        self.assertEqual((rc, out["kind"]), (0, "zp"))
        self.assertEqual(out["order"], str(ZP_ORDER))

    def test_zp_elements_print_without_a_y_coordinate(self):
        # A Z_p^* element rendered as "x,0" would not round-trip through --elem.
        rc, out = run("group", "generator", *self.ZP)
        self.assertEqual(rc, 0)
        self.assertNotIn(",", out["generator"])
        rc2, out2 = run("group", "exp", *self.ZP, "--elem", out["generator"], "--k", "1")
        self.assertEqual((rc2, out2["result"]), (0, out["generator"]))

    def test_exp_agrees_with_powmod(self):
        rc, gen = run("group", "generator", *self.ZP)
        self.assertEqual(rc, 0)
        _, viagroup = run("group", "exp", *self.ZP, "--elem", gen["generator"], "--k", "1234")
        _, viapow = run("powmod", "--base", gen["generator"], "--exp", "1234", "--mod", str(ZP_P))
        self.assertEqual(viagroup["result"], viapow["result"])

    def test_order_divides_the_group_order(self):
        rc, out = run("group", "order", *self.ZP, "--elem", "2")
        self.assertEqual(rc, 0)
        self.assertEqual(ZP_ORDER % int(out["order"]), 0)

    def test_ec_point_counting_and_lifting(self):
        rc, out = run("group", "count-points", *self.EC)
        self.assertEqual(rc, 0)
        order = out["order"]
        self.assertGreater(order, 0)
        # Some x lifts and some does not; both must be reported, not guessed.
        lifted = refused = False
        for x in range(1, 40):
            rc, out = run("group", "lift-x", *self.EC, "--order", str(order), "--x", str(x))
            if rc == 0:
                self.assertTrue(out["on_curve"])
                self.assertIn(",", out["point"])
                lifted = True
            else:
                self.assertEqual((rc, out["on_curve"]), (1, False))
                refused = True
        self.assertTrue(lifted, "no x in 1..40 lifted")
        self.assertTrue(refused, "every x in 1..40 lifted, which is suspicious")


class SolverTests(unittest.TestCase):
    ZP = ("--p", str(ZP_P), "--order", str(ZP_ORDER))

    def setUp(self):
        _, gen = run("group", "generator", *self.ZP)
        self.g = gen["generator"]
        self.x = 123456
        _, h = run("group", "exp", *self.ZP, "--elem", self.g, "--k", str(self.x))
        self.h = h["result"]

    def test_every_algorithm_finds_the_planted_log(self):
        for alg in ("bsgs", "rho", "kangaroo", "grumpy", "dlog"):
            with self.subTest(alg=alg):
                rc, out = run(
                    "solve",
                    "--alg",
                    alg,
                    *self.ZP,
                    "--g",
                    self.g,
                    "--h",
                    self.h,
                    "--lo",
                    "0",
                    "--hi",
                    str(ZP_ORDER),
                    "--seed",
                    "1",
                )
                self.assertEqual(rc, 0, out)
                self.assertEqual(int(out["x"]), self.x)
                self.assertGreater(out["stats"]["group_ops"], 0)

    def test_a_log_outside_the_interval_is_reported_not_invented(self):
        rc, out = run(
            "solve",
            "--alg",
            "bsgs",
            *self.ZP,
            "--g",
            self.g,
            "--h",
            self.h,
            "--lo",
            "0",
            "--hi",
            "100",
        )
        self.assertEqual((rc, out["found"]), (1, False))


class IndexCalculusTests(unittest.TestCase):
    def test_ic_solves_and_the_answer_checks_out(self):
        p, g, h = 1099511627791, 3, 123456789
        rc, out = run("ic", "--p", str(p), "--g", str(g), "--h", str(h), "--threads", "2")
        self.assertEqual(rc, 0)
        self.assertEqual(ca.powmod(g, int(out["x"]), p), h)
        self.assertGreater(out["factor_base"], 0)


class CheonTests(unittest.TestCase):
    def test_cheon_recovers_a_planted_alpha(self):
        # 1000002 = 2 * 3 * 166667; the prime-order subgroup is what Cheon needs.
        zp = ("--p", str(ZP_P), "--order", str(ZP_ORDER))
        _, gen = run("group", "generator", *zp)
        _, sub = run("group", "exp", *zp, "--elem", gen["generator"], "--k", "6")
        rc, out = run(
            "cheon",
            "--p",
            str(ZP_P),
            "--order",
            "166667",
            "--g",
            sub["result"],
            "--d",
            "2",
            "--alpha",
            "4242",
        )
        self.assertEqual(rc, 0, out)
        self.assertTrue(out["correct"])


class UsageTests(unittest.TestCase):
    def test_no_command_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            main([])
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_command_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            main(["not-a-command"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
