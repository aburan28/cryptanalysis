# Tests for the WDSat ANF exporter.  See RESEARCH_ECC2K130_WDSAT.md.
#
# The gate that matters is the last class: a model WDSat returns is fed
# back through the original `ir.Prog` and every root must evaluate to
# zero, and an UNSAT is checked against exhaustive search.  An exporter
# with the parity convention backwards still produces plausible-looking
# output, so nothing here trusts the solver's answer on its own.
#
# No type hints, camelCase identifiers, no itertools (project convention).

import os
import random
import shutil
import tempfile
import unittest

import ir
import wdsat

SRC = os.environ.get('WDSAT_SRC', '/tmp/ec-baseline-cache/vendor/WDSat/src')
HAVE_SRC = os.path.isdir(SRC)


def randomProg(rng, nInputs, nGates):
    """A random circuit over `nInputs` free bits, with its output roots."""
    p = ir.Prog()
    nodes = [p.addInput('v', i) for i in range(nInputs)]
    for _ in range(nGates):
        op = rng.choice(('xor', 'and', 'or', 'xor3', 'xorand', 'maj'))
        a = rng.choice(nodes)
        b = rng.choice(nodes)
        c = rng.choice(nodes)
        if op == 'xor':
            got = p.xor(a, b)
        elif op == 'and':
            got = p.andOp(a, b)
        elif op == 'or':
            got = p.orOp(a, b)
        elif op == 'xor3':
            got = p.xor(p.xor(a, b), c)
        elif op == 'xorand':
            got = p.xor(a, p.andOp(b, c))
        else:
            got = p.orOp(p.orOp(p.andOp(a, b), p.andOp(a, c)), p.andOp(b, c))
        if got is not None:
            nodes.append(got)
    roots = [rng.choice(nodes) for _ in range(2)]
    return p, roots


def brute(prog, roots, nInputs):
    """Every assignment of the free inputs that zeroes every root."""
    out = []
    for bits in range(1 << nInputs):
        vals = {}
        for i in range(nInputs):
            vals[('v', i)] = (bits >> i) & 1
        if all(v == 0 for v in prog.evaluate(vals, roots)):
            out.append(bits)
    return out


class AnfFormTests(unittest.TestCase):
    def test_parity_convention_is_inverted_on_output(self):
        # WDSat reads an equation as "these terms XOR to one", so a system
        # recording "terms XOR to zero" must emit the complementary
        # constant.  This is the trap the module docstring names.
        s = wdsat.AnfSystem()
        v = s.newVar()
        s.addEquation([(v,)], False)          # v = 0
        self.assertIn('x %d T 0' % v, s.text())
        s2 = wdsat.AnfSystem()
        v2 = s2.newVar()
        s2.addEquation([(v2,)], True)         # v + 1 = 0, i.e. v = 1
        self.assertIn('x %d 0' % v2, s2.text())

    def test_monomials_are_written_with_their_degree_prefix(self):
        s = wdsat.AnfSystem()
        a, b, c = s.newVar(), s.newVar(), s.newVar()
        s.addEquation([(a,), (b, c)], False)
        self.assertIn('x %d .2 %d %d T 0' % (a, b, c), s.text())

    def test_header_counts_equations_and_units(self):
        s = wdsat.AnfSystem()
        a = s.newVar()
        s.addEquation([(a,)], False)
        s.addUnit(a)
        self.assertTrue(s.text().startswith('p cnf 1 2\n'))

    def test_exported_gates_stay_quadratic(self):
        rng = random.Random(20260920)
        for _ in range(8):
            p, roots = randomProg(rng, 5, 25)
            s, _ = wdsat.exportAnf(p, roots)
            self.assertLessEqual(s.degree(), wdsat.MAX_MONOMIAL_DEGREE)

    def test_constant_inputs_are_folded_out(self):
        p = ir.Prog()
        a = p.addInput('a', 0)
        one = p.addInput('one', 0)
        r = p.xor(p.andOp(a, one), one)       # a*1 + 1 = a + 1
        s, varOf = wdsat.exportAnf(p, [r], assign={('one', 0): 1})
        self.assertNotIn(('one', 0), varOf)   # the constant never reaches the solver
        self.assertIn(('a', 0), varOf)
        # `a & 1` folds to a copy and costs nothing; `a + 1` still needs a
        # variable, because ANF has no negative literals to carry the
        # complement.
        self.assertEqual(s.nVars, 2)


    def test_a_repeated_input_reference_is_one_variable(self):
        # ir.Prog.addInput appends unconditionally, so a builder that adds
        # ('a', 0) twice gets two nodes for one value.  emitCnf collapses
        # them through its literal map; the ANF exporter must agree, or a
        # constraint written about the second copy constrains nothing.
        p = ir.Prog()
        first = p.addInput('a', 0)
        second = p.addInput('a', 0)
        s, varOf = wdsat.exportAnf(p, [p.xor(first, second)])
        self.assertEqual(s.nVars, 1)
        self.assertEqual(len(varOf), 1)


class ConfigTests(unittest.TestCase):
    def test_sizes_cover_the_instance(self):
        s = wdsat.AnfSystem()
        for _ in range(40):
            s.newVar()
        s.addEquation([(1,), (2, 3)], False)
        template = '#define __MAX_ANF_ID__ 23\n#define __MAX_DEGREE__ 3\n' \
                   '#define __MAX_ID__ 100\n#define __XG_ENHANCED__\n'
        header, values = wdsat.configHeader(s, template)
        self.assertGreater(values['__MAX_ANF_ID__'], s.nVars)
        self.assertGreater(values['__MAX_ID__'], s.nVars)
        self.assertGreaterEqual(values['__MAX_DEGREE__'], s.degree() + 1)
        # Switches the caller set are not ours to change.
        self.assertIn('#define __XG_ENHANCED__', header)
        self.assertIn('#define __MAX_ANF_ID__ %d' % values['__MAX_ANF_ID__'], header)


@unittest.skipUnless(HAVE_SRC, 'WDSat sources not built; see the note')
class SolverAgreementTests(unittest.TestCase):
    """The real gate: WDSat's verdict against exhaustive search, and its
    models against the IR they came from."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='wdsat-test-')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, p, roots, nInputs):
        s, varOf = wdsat.exportAnf(p, roots)
        exe, _ = wdsat.buildSolver(SRC, s, self.tmp)
        path = os.path.join(self.tmp, 'instance.anf')
        verdict = wdsat.solve(exe, s, path, timeout=120)
        expected = brute(p, roots, nInputs)
        self.assertIsNotNone(verdict.sat, 'solver timed out')
        self.assertEqual(verdict.sat, bool(expected),
                         'verdict disagrees with exhaustive search')
        if not verdict.sat:
            return
        vals = {}
        for i in range(nInputs):
            var = varOf.get(('v', i))
            bit = 0 if var is None else verdict.value(var)
            self.assertIsNotNone(bit, 'model leaves an input undefined')
            vals[('v', i)] = bit
        self.assertTrue(all(v == 0 for v in p.evaluate(vals, roots)),
                        'model does not zero the roots it was solved for')

    def test_random_systems_agree_with_exhaustive_search(self):
        rng = random.Random(0xC0FFEE)
        for _ in range(12):
            p, roots = randomProg(rng, 6, 18)
            self.check(p, roots, 6)

    def test_an_unsatisfiable_system_is_refuted(self):
        p = ir.Prog()
        a = p.addInput('v', 0)
        one = p.addInput('one', 0)
        # a = 0 and a = 1 at once.
        s, _ = wdsat.exportAnf(p, [a, p.xor(a, one)], assign={('one', 0): 1})
        exe, _ = wdsat.buildSolver(SRC, s, self.tmp)
        verdict = wdsat.solve(exe, s, os.path.join(self.tmp, 'unsat.anf'),
                              timeout=120)
        self.assertIs(verdict.sat, False)

    def test_conflicts_are_reported(self):
        rng = random.Random(7)
        p, roots = randomProg(rng, 6, 18)
        s, _ = wdsat.exportAnf(p, roots)
        exe, _ = wdsat.buildSolver(SRC, s, self.tmp)
        verdict = wdsat.solve(exe, s, os.path.join(self.tmp, 'conf.anf'),
                              timeout=120)
        self.assertIsNotNone(verdict.conflicts)
        self.assertGreaterEqual(verdict.conflicts, 0)


if __name__ == '__main__':
    unittest.main()
