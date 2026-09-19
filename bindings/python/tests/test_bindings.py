"""End-to-end tests for the Python bindings, mirroring tests/test_ffi.c.

Run with:  cd bindings/python && python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import ctypes
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cryptanalysis as ca

# The package re-exports the private module, so one import form covers both.
_lib = ca._lib

# Same instances as tests/test_ffi.c
ZP_P = 2000000579
ZP_ORDER = 1000000289
ZP_X = 123456789
EC_P, EC_A, EC_B = 1000003, 1, 7
IC_P = 1000003


class StructAndLoaderTests(unittest.TestCase):
    def test_struct_sizes_match_library(self):
        lib = _lib.lib
        self.assertEqual(ctypes.sizeof(_lib.COptions), lib.ca_ffi_options_size())
        self.assertEqual(ctypes.sizeof(_lib.CStats), lib.ca_stats_size())
        self.assertEqual(ctypes.sizeof(_lib.CICParams), lib.ca_ic_params_size())
        self.assertEqual(ctypes.sizeof(_lib.CICStats), lib.ca_ic_stats_size())
        # Sanity: the documented layouts on LP64 platforms.
        self.assertEqual(ctypes.sizeof(_lib.COptions), 104)
        self.assertEqual(ctypes.sizeof(_lib.CStats), 56)
        self.assertEqual(ctypes.sizeof(_lib.CICParams), 48)
        self.assertEqual(ctypes.sizeof(_lib.CICStats), 64)

    def test_version(self):
        self.assertEqual(ca.version(), "0.1.0")
        self.assertEqual(ca.__version__, ca.version())
        self.assertTrue(os.path.exists(ca.library_path) or os.sep not in ca.library_path)

    def test_options_defaults_match_library(self):
        self.assertEqual(ca.Options(), ca.Options.library_defaults())
        c = ca.Options().to_c()
        d = _lib.COptions()
        _lib.lib.ca_ffi_options_default(ctypes.byref(d))
        for name, _ in _lib.COptions._fields_:
            self.assertEqual(getattr(c, name), getattr(d, name), name)
        self.assertEqual(ca.Options.from_c(c), ca.Options())

    def test_ic_params_defaults_match_library(self):
        self.assertEqual(ca.ICParams(), ca.ICParams.library_defaults())
        c = ca.ICParams(seed=3, verbose=True, method=ca.ICMethod.RANDOM_EXPONENT).to_c()
        self.assertEqual(c.seed, 3)
        self.assertEqual(c.verbose, 1)
        self.assertEqual(c.method, 1)

    def test_status_strings(self):
        self.assertEqual(ca.status_string(0), "ok")
        self.assertEqual(ca.status_string(ca.Status.NOT_FOUND), "not found")


class ZpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.G = ca.Group.zp(ZP_P, ZP_ORDER)
        cls.g = cls.G.find_generator(seed=1)
        cls.h = cls.G.mul(cls.g, ZP_X)
        cls.opts = ca.Options(seed=7)

    @classmethod
    def tearDownClass(cls):
        cls.G.close()

    def test_group_properties(self):
        G = self.G
        self.assertEqual(G.kind, ca.GroupKind.ZP)
        self.assertEqual(G.p, ZP_P)
        self.assertEqual(G.order, ZP_ORDER)
        self.assertIn("zp", repr(G))

    def test_bad_modulus_raises_invalid(self):
        with self.assertRaises(ca.InvalidError) as cm:
            ca.Group.zp(1000)
        self.assertEqual(cm.exception.status, ca.Status.INVALID)
        self.assertIn("not an odd prime", str(cm.exception))

    def test_validate(self):
        G = self.G
        self.assertTrue(G.validate(self.g))
        self.assertFalse(G.validate(0))
        self.assertFalse(G.validate((0, 0, 0, 0)))
        self.assertFalse(G.validate(ZP_P))
        self.assertFalse(G.validate("nope"))
        self.assertTrue(G.validate(self.g.x))  # plain int convenience

    def test_element_ops(self):
        G, g = self.G, self.g
        t = G.op(g, g)
        self.assertEqual(t, G.mul(g, 2))
        self.assertTrue(G.equal(t, G.mul(g, 2)))
        self.assertTrue(G.is_identity(G.op(G.inv(g), g)))
        self.assertEqual(G.identity(), ca.Elem(1))
        self.assertEqual(G.elem_order(g), ZP_ORDER)
        self.assertEqual(int(g), g.x)
        # tuples and ints are accepted as elements
        self.assertEqual(G.op(g.x, (g.x,)), t)

    def test_invalid_element_raises(self):
        with self.assertRaises(ca.InvalidError) as cm:
            self.G.op(0, self.g)
        self.assertIn("not in the group", str(cm.exception))
        with self.assertRaises(TypeError):
            self.G.op("x", self.g)
        with self.assertRaises(OverflowError):
            self.G.mul(self.g, 1 << 64)
        with self.assertRaises(OverflowError):
            self.G.mul(self.g, -1)

    def test_bsgs(self):
        x, st = self.G.bsgs(self.g, self.h, options=self.opts)
        self.assertEqual(x, ZP_X)
        self.assertIsInstance(st, ca.Stats)
        self.assertGreater(st.group_ops, 0)

    def test_bsgs_interval(self):
        x, _ = self.G.bsgs(self.g, self.h, 123000000, 124000000, self.opts)
        self.assertEqual(x, ZP_X)

    def test_rho(self):
        x, st = self.G.rho(self.g, self.h, self.opts)
        self.assertEqual(x, ZP_X)
        self.assertGreater(st.group_ops, 0)

    def test_kangaroo(self):
        x, _ = self.G.kangaroo(self.g, self.h, 123000000, 124000000, self.opts)
        self.assertEqual(x, ZP_X)

    def test_grumpy(self):
        x, _ = self.G.grumpy(self.g, self.h, 123000000, 124000000, self.opts)
        self.assertEqual(x, ZP_X)

    def test_dlog_auto_and_each_solver(self):
        x, _ = self.G.dlog(self.g, self.h, self.opts)
        self.assertEqual(x, ZP_X)
        x, _ = self.G.dlog(self.g, self.h)  # NULL options
        self.assertEqual(x, ZP_X)
        for solver in (ca.Solver.BSGS, ca.Solver.RHO, ca.Solver.KANGAROO, ca.Solver.GRUMPY):
            x, _ = self.G.dlog(self.g, self.h, ca.Options(seed=7, solver=solver))
            self.assertEqual(x, ZP_X, solver)

    def test_interval_excluding_x_raises_not_found(self):
        with self.assertRaises(ca.NotFoundError) as cm:
            self.G.bsgs(self.g, self.h, 1, 1000, self.opts)
        self.assertEqual(cm.exception.status, ca.Status.NOT_FOUND)
        self.assertIsInstance(cm.exception, ca.CryptanalysisError)
        # The message must not inherit an earlier, unrelated ca_last_error().
        self.assertNotIn("not in the group", str(cm.exception))

    def test_max_ops_raises_limit(self):
        with self.assertRaises(ca.LimitError) as cm:
            self.G.bsgs(self.g, self.h, options=ca.Options(seed=7, max_ops=1))
        self.assertEqual(cm.exception.status, ca.Status.LIMIT)
        with self.assertRaises(ca.LimitError):
            self.G.grumpy(self.g, self.h, 123000000, 124000000, ca.Options(max_ops=3))

    def test_lift_x_unsupported_for_zp(self):
        with self.assertRaises(ca.UnsupportedError):
            self.G.lift_x(5)

    def test_cheon(self):
        G, g = self.G, self.g
        d, cost = ca.cheon_best_divisor(ZP_ORDER)
        self.assertGreater(d, 1)
        self.assertEqual((ZP_ORDER - 1) % d, 0)
        self.assertGreater(cost, 0.0)
        ga, gad = G.cheon_instance(g, 987654321, d)
        self.assertEqual(ga, G.mul(g, 987654321))
        alpha, st = G.cheon(g, ga, gad, d)
        self.assertEqual(alpha, 987654321)
        self.assertIsInstance(st, ca.Stats)

    def test_cheon_bad_divisor(self):
        with self.assertRaises(ca.InvalidError) as cm:
            self.G.cheon_instance(self.g, 5, 11)  # 11 does not divide order-1
        self.assertIn("divide", str(cm.exception))

    def test_context_manager_and_close(self):
        with ca.Group.zp(ZP_P, ZP_ORDER) as G:
            self.assertFalse(G.closed)
            self.assertEqual(G.p, ZP_P)
        self.assertTrue(G.closed)
        with self.assertRaises(ValueError):
            G.identity()
        G.close()  # idempotent

    def test_random_element(self):
        e = self.G.random_element(seed=5)
        self.assertTrue(self.G.validate(e))
        self.assertEqual(e, self.G.random_element(seed=5))


class EcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.n = ca.Group.ec_count_points(EC_P, EC_A, EC_B)
        cls.E = ca.Group.ec(EC_P, EC_A, EC_B, cls.n)

    @classmethod
    def tearDownClass(cls):
        cls.E.close()

    def test_singular_curve_rejected(self):
        with self.assertRaises(ca.InvalidError) as cm:
            ca.Group.ec(97, 0, 0)
        self.assertIn("singular", str(cm.exception))

    def test_properties(self):
        E = self.E
        self.assertEqual(E.kind, ca.GroupKind.EC)
        self.assertEqual((E.p, E.a, E.b), (EC_P, EC_A, EC_B))
        self.assertEqual(E.order, self.n)
        # Hasse bound
        self.assertLess(abs(self.n - (EC_P + 1)), 2 * int(EC_P**0.5) + 2)

    def test_points_and_dlog(self):
        E = self.E
        P = E.random_element(seed=3)
        self.assertFalse(P.inf)
        self.assertTrue(E.validate(P))
        self.assertFalse(E.validate(ca.Elem(P.x, P.y ^ 1)))
        self.assertFalse(E.validate((P.x, P.y ^ 1)))
        ord_P = E.elem_order(P)
        E.set_order(ord_P, self.n // ord_P)
        self.assertEqual(E.order, ord_P)
        self.assertEqual(E.cofactor, self.n // ord_P)
        Q = E.mul(P, 4242)
        x, _st = E.dlog(P, Q)
        self.assertEqual(x, 4242 % ord_P)
        self.assertEqual(E.bsgs(P, Q)[0], 4242 % ord_P)
        self.assertEqual(E.rho(P, Q, ca.Options(seed=7))[0], 4242 % ord_P)
        inf = E.identity()
        self.assertTrue(inf.inf)
        self.assertTrue(E.is_identity(inf))
        self.assertTrue(E.is_identity(E.op(P, E.inv(P))))
        self.assertEqual(E.op(P, inf), P)
        R = E.lift_x(P.x)
        self.assertEqual(R.x, P.x)
        self.assertIn(R.y, (P.y, EC_P - P.y))
        E.set_order(self.n, 0)

    def test_ints_rejected_for_curve_points(self):
        with self.assertRaises(TypeError):
            self.E.validate_strict = self.E.op(5, 6)

    def test_lift_x_not_found(self):
        # Half the x's have no point; find one deterministically.
        for x in range(1, 200):
            try:
                self.E.lift_x(x)
            except ca.NotFoundError as exc:
                self.assertEqual(exc.status, ca.Status.NOT_FOUND)
                break
        else:
            self.fail("expected some x without a point")


class IndexCalculusTests(unittest.TestCase):
    def test_ic_solve(self):
        x, st = ca.ic_solve(IC_P, 2, 424242, ca.ICParams(seed=3))
        self.assertEqual(ca.powmod(2, x, IC_P), 424242)
        self.assertIsInstance(st, ca.ICStats)
        self.assertGreater(st.factor_base_size, 0)
        self.assertGreater(st.relations, 0)

    def test_ic_solve_default_params(self):
        x, _ = ca.ic_solve(IC_P, 2, 424242)
        self.assertEqual(ca.powmod(2, x, IC_P), 424242)

    def test_ic_context(self):
        with ca.ICContext(IC_P, 2, ca.ICParams(seed=3)) as ctx:
            self.assertEqual(ctx.p, IC_P)
            self.assertEqual(ctx.g, 2)
            self.assertGreater(ctx.factor_base_size, 0)
            self.assertEqual(ctx.factor_base_size, ctx.stats.factor_base_size)
            self.assertEqual(ctx.primitive_root, 2)
            logs = ctx.factor_base_logs()
            self.assertEqual(len(logs), ctx.factor_base_size)
            for prime, lg in logs:
                self.assertIsNotNone(lg)
                self.assertEqual(ca.powmod(ctx.primitive_root, lg, IC_P), prime)
            for h in (424242, 3, 999999):
                x, st = ctx.log(h)
                self.assertEqual(ca.powmod(2, x, IC_P), h)
                self.assertIsInstance(st, ca.Stats)
        self.assertIn("closed", repr(ctx))
        with self.assertRaises(ValueError):
            ctx.log(3)

    def test_ic_bad_modulus(self):
        with self.assertRaises(ca.InvalidError):
            ca.ic_solve(1000, 2, 3)

    def test_ic_auto_params(self):
        B, C = ca.ic_auto_params(20)
        self.assertGreater(B, 0)
        self.assertGreater(C, 0)


class NumberTheoryTests(unittest.TestCase):
    def test_helpers(self):
        self.assertTrue(ca.is_prime(1000003))
        self.assertFalse(ca.is_prime(1000002))
        self.assertTrue(ca.is_prime(ZP_P))
        self.assertEqual(ca.next_prime(1000003), 1000033)
        self.assertEqual(ca.primitive_root(1000003), 2)
        self.assertEqual(ca.powmod(2, 20, 1000003), pow(2, 20, 1000003))
        self.assertEqual(ca.invmod(3, 1000003), pow(3, -1, 1000003))
        self.assertEqual(ca.factorize(1000002), [(2, 1), (3, 1), (166667, 1)])
        self.assertEqual(ca.factorize(2**10 * 3**3), [(2, 10), (3, 3)])
        self.assertEqual(ca.factorize(1), [])

    def test_64bit_range(self):
        big = (1 << 64) - 59  # the largest 64-bit prime
        self.assertTrue(ca.is_prime(big))
        self.assertEqual(ca.powmod(3, big - 1, big), 1)
        with self.assertRaises(OverflowError):
            ca.is_prime(1 << 64)
        with self.assertRaises(OverflowError):
            ca.powmod(-1, 2, 7)
        with self.assertRaises(TypeError):
            ca.is_prime(7.0)


if __name__ == "__main__":
    unittest.main()
