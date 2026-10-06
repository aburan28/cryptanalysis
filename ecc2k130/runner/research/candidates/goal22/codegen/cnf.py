# CNF construction for the index-calculus point decomposition.
#
# The expensive part of a decomposition instance is F_2^m multiplication, and
# the generator already emits a near-minimal straight-line circuit for it.
# Encoding that circuit with Tseitin costs a few gates per bit operation, where
# encoding a multiplication from its definition would cost m^3 AND terms: at
# m=131 that is 15588 gates against 2.2 million.  So the SAT front end is not a
# new piece of arithmetic, it is one more back end for the IR that already
# exists -- see Prog.emitCnf, which is emit() with clauses instead of C.
#
# The circuit is XOR-dominated, so an XOR-aware solver matters more here than
# the choice of encoding: XOR clauses are handed to the solver natively rather
# than expanded to four clauses each, which lets Gaussian elimination run
# inside the search.  writeDimacs emits them in the CryptoMiniSat 'x' form.
#
# No type hints, camelCase identifiers, no itertools (project convention).


class Cnf:
    """A CNF with native XOR clauses and a constant-true variable.

    Variable 1 is asserted true, so `true` and `false` are ordinary literals and
    constant folding needs no special cases anywhere else."""

    def __init__(self):
        self.nVars = 1
        self.clauses = [[1]]
        self.xors = []
        self.true = 1
        self.false = -1

    def newVar(self):
        self.nVars += 1
        return self.nVars

    def addClause(self, lits):
        self.clauses.append(list(lits))

    def addXor(self, lits, rhs):
        """XOR of `lits` equals `rhs` (a bool)."""
        pos = []
        for l in lits:
            if l < 0:
                rhs = not rhs
                pos.append(-l)
            else:
                pos.append(l)
        self.xors.append((pos, rhs))

    # ---- gates, with constant folding ---------------------------------
    def xorLit(self, a, b):
        if a == self.false:
            return b
        if b == self.false:
            return a
        if a == self.true:
            return -b
        if b == self.true:
            return -a
        if a == b:
            return self.false
        if a == -b:
            return self.true
        z = self.newVar()
        self.addXor([a, b, z], False)
        return z

    def andLit(self, a, b):
        if a == self.false or b == self.false:
            return self.false
        if a == self.true:
            return b
        if b == self.true:
            return a
        if a == b:
            return a
        if a == -b:
            return self.false
        z = self.newVar()
        self.addClause([-z, a])
        self.addClause([-z, b])
        self.addClause([z, -a, -b])
        return z

    def orLit(self, a, b):
        return -self.andLit(-a, -b)

    def majLit(self, a, b, c):
        z = self.newVar()
        self.addClause([-z, a, b])
        self.addClause([-z, a, c])
        self.addClause([-z, b, c])
        self.addClause([z, -a, -b])
        self.addClause([z, -a, -c])
        self.addClause([z, -b, -c])
        return z

    def assertZero(self, lit):
        if lit == self.true:
            raise ValueError('unsatisfiable by construction: asserted 1 == 0')
        if lit != self.false:
            self.addClause([-lit])

    # ---- constraints ---------------------------------------------------
    def atMost(self, lits, k):
        """Sinz sequential counter: at most k of `lits` are true.  O(n k).

        This is the constraint a Groebner-based decomposition cannot use.  A
        factor base cut out by a linear subspace keeps the Weil descent low
        degree; a factor base cut out by Hamming weight does not, but weight is
        invariant under the Frobenius for every field size, where a Frobenius
        stable subspace exists only when 2 has small order mod m."""
        n = len(lits)
        if k >= n:
            return
        if k == 0:
            for l in lits:
                self.addClause([-l])
            return
        s = []
        for i in range(n - 1):
            s.append([self.newVar() for _ in range(k)])
        self.addClause([-lits[0], s[0][0]])
        for j in range(1, k):
            self.addClause([-s[0][j]])
        for i in range(1, n - 1):
            self.addClause([-lits[i], s[i][0]])
            self.addClause([-s[i - 1][0], s[i][0]])
            for j in range(1, k):
                self.addClause([-lits[i], -s[i - 1][j - 1], s[i][j]])
                self.addClause([-s[i - 1][j], s[i][j]])
            self.addClause([-lits[i], -s[i - 1][k - 1]])
        self.addClause([-lits[n - 1], -s[n - 2][k - 1]])

    def lexLeq(self, a, b):
        """a <= b as bit vectors, most significant first.

        Used twice: to order the m factor base points against each other, which
        kills the m! ways of writing the same decomposition, and to pin each
        point to the lexicographically least of its Frobenius images, which
        kills the m rotations of each.  Together that is m! * m assignments per
        genuine solution -- 3144 at m=4 over F_2^131."""
        eq = self.true
        for i in range(len(a)):
            self.addClause([-eq, -a[i], b[i]])
            same = -self.xorLit(a[i], b[i])
            eq = self.andLit(eq, same)

    # ---- output ---------------------------------------------------------
    def writeDimacs(self, path):
        fh = open(path, 'w')
        fh.write('p cnf %d %d\n' % (self.nVars, len(self.clauses) + len(self.xors)))
        for c in self.clauses:
            fh.write(' '.join(str(l) for l in c) + ' 0\n')
        for lits, rhs in self.xors:
            head = 'x' if rhs else 'x-'
            fh.write(head + str(lits[0]) + ' '
                     + ' '.join(str(l) for l in lits[1:]) + ' 0\n')
        fh.close()

    def stats(self):
        return {'vars': self.nVars, 'clauses': len(self.clauses),
                'xors': len(self.xors)}
