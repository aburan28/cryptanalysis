"""Export an `ir.Prog` as a WDSat ANF instance, and size a `config.h` for it.

WDSat (Trimoska, Ionica, Dequen, CP20) is a SAT solver written for
instances derived from a Weil descent: its XORGAUSS-extended module does
Gaussian elimination over the XOR part, which is most of what a descended
elliptic system is.  This repository already vendors and builds it for the
frozen S4 regression
(`research/index_calculus_baseline_20260914/`); what was missing is a way
to put *our own* encodings in front of it.

Two things make that non-obvious, and both are properties of WDSat rather
than choices made here.

**ANF mode takes no OR-clauses.**  With `__XG_ENHANCED__` defined -- which
is what makes the solver worth using, and what the frozen build defines --
`dimacs.c` parses a line starting with `x` as an XOR-of-monomials equation
and *any other line as a single-literal unit clause*.  There is no branch
that reads a general OR-clause.  So a constraint that is naturally a
disjunction (`this vector is nonzero`, `these two abscissas differ`) cannot
be handed to the solver in this mode at all.  `exportAnf` therefore emits
the equational part only, and the caller filters the models it gets back.
See `RESEARCH_ECC2K130_WDSAT.md`.

**The binary is dimension-pinned.**  WDSat's core structures are statically
allocated, so `__MAX_ANF_ID__`, `__MAX_DEGREE__`, `__MAX_ID__` and the
buffer caps are compile-time constants that must fit the instance.  A
different encoding is a different binary.  `configHeader` emits those
constants from a measured instance rather than from a guess; the solver
alerts on an underestimated `__MAX_ID__` but an underestimated
`__MAX_XEQ_SIZE__` can fail late, so it is sized generously.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import ir


# One ANF equation per gate, in the Tseitin style: a fresh variable for
# every gate output, constrained to equal the gate's function of its
# inputs.  Every equation is then linear or quadratic except MAJ, which is
# quadratic too, so the whole system fits __MAX_DEGREE__ = 3 ("make it +1",
# i.e. monomials of degree at most 2).
MAX_MONOMIAL_DEGREE = 2


class AnfSystem:
    """An ANF system over variables `1 .. nVars`, as WDSat reads them.

    `equations` is a list of (monomials, constant): the XOR of the
    monomials plus the constant is zero.  A monomial is a tuple of
    variables, so `()` cannot occur -- a constant is carried by the flag.
    `units` are single-literal assertions, the one non-XOR line the ANF
    parser accepts.
    """

    def __init__(self):
        self.nVars = 0
        self.equations = []
        self.units = []

    def newVar(self):
        self.nVars += 1
        return self.nVars

    def addEquation(self, monomials, constant=False):
        terms = []
        for mono in monomials:
            terms.append(tuple(sorted(set(mono))))
        self.equations.append((terms, bool(constant)))

    def addUnit(self, lit):
        self.units.append(lit)

    def degree(self):
        best = 1
        for terms, _ in self.equations:
            for mono in terms:
                if len(mono) > best:
                    best = len(mono)
        return best

    def monomialColumns(self):
        """Distinct monomials of degree at least two.

        WDSat gives each one a column in its CNF-XOR view, so
        `__MAX_ID__` has to cover the unary variables *and* these -- the
        README's "maximum number of variables in the CNF-XOR form, ...
        even when the given input is in ANF".  Sizing it from the unary
        count alone builds a solver that segfaults on a large instance
        instead of alerting, because `monomials_to_column` is indexed by
        both.
        """
        seen = set()
        for terms, _ in self.equations:
            for mono in terms:
                if len(mono) > 1:
                    seen.add(mono)
        return len(seen)

    def maxEquationSize(self):
        best = 1
        for terms, constant in self.equations:
            size = len(terms) + (1 if constant else 0)
            if size > best:
                best = size
        return best

    def text(self):
        """The instance in WDSat's ANF form.

        **WDSat's XOR equations assert parity one, not zero.**  `dimacs.c`
        absorbs a `T` by negating the equation's first literal, and the
        solver then requires the literals to XOR to true; a line with no
        `T` means "these terms XOR to 1".  `equations` here records the
        ordinary "terms XOR to `constant`" form, so the emitted constant
        is the complement.  Getting this backwards yields a solver that
        answers a different question and still looks like it works, which
        is why `testwdsat.py` checks models against the original IR.
        """
        lines = ['p cnf %d %d' % (self.nVars, len(self.equations) + len(self.units))]
        for terms, constant in self.equations:
            parts = ['x']
            for mono in terms:
                if len(mono) == 1:
                    parts.append(str(mono[0]))
                else:
                    parts.append('.%d' % len(mono))
                    for v in mono:
                        parts.append(str(v))
            if not constant:
                parts.append('T')
            parts.append('0')
            lines.append(' '.join(parts))
        for lit in self.units:
            lines.append('%d 0' % lit)
        return '\n'.join(lines) + '\n'

    def write(self, path):
        fh = open(path, 'w')
        fh.write(self.text())
        fh.close()
        return path


def exportAnf(prog, roots, assign=None):
    """Turn a straight-line `ir.Prog` into an `AnfSystem`.

    `assign` maps an input reference `(arrayName, position)` to a constant
    bit, for the inputs the caller has already fixed -- the target
    coordinates, the field unit.  Unassigned inputs become free variables.

    Returns `(system, varOf)` where `varOf` maps an input reference to its
    variable number, so the caller can read a model back.  Inputs that
    were assigned a constant do not appear in it.

    Every root is asserted zero, which is what makes the system say
    "this decomposition holds".
    """
    system = AnfSystem()
    varOf = {}
    # Node -> (kind, payload).  A node is either the constant 0, the
    # constant 1, or a variable; folding the constants here keeps them out
    # of the emitted equations, where WDSat would have to carry them.
    ZERO, ONE, VAR = 0, 1, 2
    val = [None] * len(prog.ops)

    def constant(bit):
        return (ONE, None) if bit else (ZERO, None)

    for i in range(len(prog.ops)):
        src = prog.inputRef[i]
        if src is not None:
            if assign is not None and src in assign:
                val[i] = constant(assign[src])
            elif src in varOf:
                # `addInput` appends a node every time it is called, so one
                # reference can name several nodes.  `emitCnf` maps them all
                # to a single literal, and so must this: giving the second
                # node its own variable silently decouples constraints that
                # were written about the same value, and the system stays
                # satisfiable while meaning something else.
                val[i] = (VAR, varOf[src])
            else:
                v = system.newVar()
                varOf[src] = v
                val[i] = (VAR, v)
            continue
        node = prog.ops[i]
        if node is None:
            continue
        val[i] = _emitGate(system, node, val)

    for r in roots:
        if r is None:
            continue
        kind, payload = val[r]
        if kind == ZERO:
            continue
        if kind == ONE:
            # The system is unsatisfiable before the solver sees it.  Say
            # so with a contradictory pair of units rather than silently
            # dropping the root.
            v = system.newVar()
            system.addUnit(v)
            system.addUnit(-v)
            continue
        system.addEquation([(payload,)], False)
    return system, varOf


def _emitGate(system, node, val):
    """One gate: a fresh variable and the equation defining it."""
    ZERO, ONE, VAR = 0, 1, 2
    op, args = node
    kinds = [val[a] for a in args]

    def lit(k):
        return kinds[k]

    def asMonomialList(pairs):
        """Fold constants out of a list of (coefficient-1) monomials."""
        terms = []
        constant = False
        for mono in pairs:
            if mono is None:
                continue
            if mono == ():
                constant = not constant
                continue
            terms.append(mono)
        return terms, constant

    def monoOf(k):
        """The monomial for a single operand: None if it is zero."""
        kind, payload = lit(k)
        if kind == ZERO:
            return None
        if kind == ONE:
            return ()
        return (payload,)

    def productOf(ks):
        """The monomial for a product of operands: None if any is zero."""
        vars_ = []
        for k in ks:
            kind, payload = lit(k)
            if kind == ZERO:
                return None
            if kind == ONE:
                continue
            vars_.append(payload)
        if not vars_:
            return ()
        return tuple(sorted(set(vars_)))

    if op == ir.OP_XOR:
        pieces = [monoOf(0), monoOf(1)]
    elif op == ir.OP_XOR3:
        pieces = [monoOf(0), monoOf(1), monoOf(2)]
    elif op == ir.OP_AND:
        pieces = [productOf([0, 1])]
    elif op == ir.OP_XORAND:
        pieces = [monoOf(0), productOf([1, 2])]
    elif op == ir.OP_MAJ:
        pieces = [productOf([0, 1]), productOf([0, 2]), productOf([1, 2])]
    elif op == ir.OP_OR:
        pieces = [monoOf(0), monoOf(1), productOf([0, 1])]
    elif op == ir.OP_NOT:
        pieces = [monoOf(0), ()]
    else:
        raise ValueError('no ANF rule for op %s' % op)

    terms, constant = asMonomialList(pieces)
    # Cancel repeated monomials: over GF(2) a term twice is no term.
    counted = {}
    for mono in terms:
        counted[mono] = counted.get(mono, 0) + 1
    terms = [mono for mono in counted if counted[mono] % 2]

    if not terms:
        return (ONE, None) if constant else (ZERO, None)
    if len(terms) == 1 and len(terms[0]) == 1 and not constant:
        # A pure copy needs no new variable or equation.
        return (VAR, terms[0][0])

    out = system.newVar()
    system.addEquation([(out,)] + terms, constant)
    return (VAR, out)


def configHeader(system, template, slack=2):
    """Rewrite a WDSat `config.h` so its static structures fit `system`.

    `template` is the vendored header's text.  The constants WDSat's own
    README calls out are replaced; everything else, including the
    `__XG_ENHANCED__` and `__FIND_ALL_SOLUTIONS__` switches, is left as
    the caller's template set it.

    `slack` multiplies the sizes that WDSat can grow at run time --
    XOR-clause size grows under Gaussian elimination, and the README warns
    an underestimate there fails late rather than immediately.
    """
    degree = system.degree()
    columns = system.monomialColumns()
    # `monomials_to_column` is __MAX_ANF_ID__ x (__MAX_ID__ + 1) x
    # (__MAX_DEGREE__ - 1), so __MAX_ID__ is quadratic in the instance and
    # a loose bound costs hundreds of megabytes of .bss.  Size it from the
    # monomials actually present.
    values = {
        '__MAX_ANF_ID__': system.nVars + 1,
        '__MAX_DEGREE__': max(degree, MAX_MONOMIAL_DEGREE) + 1,
        # WDSat prints the exact value it wanted; this formula reproduces
        # it, which is the check that the column count above is right.
        '__MAX_ID__': system.nVars + columns,
        '__MAX_BUFFER_SIZE__': max(30000, len(system.equations) * 20),
        '__MAX_EQ__': max(6000, len(system.units) * 4 + 16),
        '__MAX_EQ_SIZE__': max(degree, MAX_MONOMIAL_DEGREE) + 2,
        '__MAX_XEQ__': max(200, len(system.equations) * 2),
        '__MAX_XEQ_SIZE__': max(500, system.nVars + columns),
    }
    out = []
    for line in template.split('\n'):
        stripped = line.strip()
        replaced = False
        for name, value in values.items():
            if stripped.startswith('#define %s ' % name):
                out.append('#define %s %d' % (name, value))
                replaced = True
                break
        if not replaced:
            out.append(line)
    return '\n'.join(out), values


# ---------------------------------------------------------------------------
# Building and running the solver
# ---------------------------------------------------------------------------

SOLVER_SOURCES = ('cnf.c', 'dimacs.c', 'main.c', 'wdsat.c', 'wdsat_utils.c',
                  'xorgauss.c', 'xorset.c')


def buildSolver(srcDir, system, outDir, cc='gcc', slack=2):
    """Compile a WDSat sized for `system`, returning (path, config values).

    The vendored tree is copied so its `config.h` is never edited in
    place: the frozen regression's binary must stay reproducible from the
    manifest.  Builds are cached on the config values, because a ladder
    re-uses one shape for many instances.
    """
    import hashlib
    import os
    import shutil
    import subprocess

    fh = open(os.path.join(srcDir, 'config.h'))
    template = fh.read()
    fh.close()
    header, values = configHeader(system, template, slack)
    key = hashlib.sha256(header.encode()).hexdigest()[:16]
    exe = os.path.join(outDir, 'wdsat_%s' % key)
    if os.path.exists(exe):
        return exe, values
    os.makedirs(outDir, exist_ok=True)
    build = os.path.join(outDir, 'src_%s' % key)
    if os.path.exists(build):
        shutil.rmtree(build)
    shutil.copytree(srcDir, build)
    fh = open(os.path.join(build, 'config.h'), 'w')
    fh.write(header)
    fh.close()
    # `-mcmodel=medium`: WDSat's structures are static arrays sized by
    # config.h, and past a few thousand variables their combined .bss
    # exceeds what the small code model can address -- the link fails with
    # "relocation truncated to fit" rather than anything about the
    # instance.  The medium model costs nothing here and is what makes a
    # larger encoding linkable at all.
    cmd = [cc, '-O3', '-w', '-mcmodel=medium'] \
        + [os.path.join(build, f) for f in SOLVER_SOURCES] + ['-lm', '-o', exe]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError('WDSat build failed: %s' % proc.stderr[-2000:])
    return exe, values


class Verdict:
    """What one WDSat run concluded.

    `sat` is None when the run did not decide, which is neither a model
    nor a refutation and must not be counted as either.  `outcome` says
    which kind of non-decision it was: a `timeout` is the budget running
    out, an `error` is the solver dying -- a statically allocated solver
    given the wrong `config.h` segfaults rather than complaining, and
    reporting that as a timeout would read as "the instance is hard" when
    it means "the build was wrong".  `conflicts` is the solver's own
    counter, the same one the frozen regression compares.
    """

    def __init__(self, sat, model, conflicts, seconds, stdout, outcome=None):
        self.sat = sat
        self.model = model
        self.conflicts = conflicts
        self.seconds = seconds
        self.stdout = stdout
        if outcome is not None:
            self.outcome = outcome
        elif sat is None:
            self.outcome = 'undecided'
        else:
            self.outcome = 'sat' if sat else 'unsat'

    def value(self, var):
        """The bit assigned to variable `var`, or None if undefined.

        WDSat prints `__TRUE__ = 1`, `__FALSE__ = 0` and `__UNDEF__ = 2`
        per unary variable, in variable order.
        """
        if self.model is None or var > len(self.model):
            return None
        ch = self.model[var - 1]
        return None if ch == '2' else int(ch)


def solve(exe, system, path, timeout=None, gaussian=True):
    """Run the solver on `system`, written to `path`."""
    import subprocess
    import time

    system.write(path)
    cmd = [exe, '-i', path]
    if gaussian:
        cmd.append('-x')
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Verdict(None, None, None, timeout, '', outcome='timeout')
    seconds = time.time() - start
    if proc.returncode != 0:
        return Verdict(None, None, None, seconds,
                       proc.stdout + proc.stderr,
                       outcome='error:rc=%d' % proc.returncode)
    lines = []
    for line in proc.stdout.split('\n'):
        if line and '!!!' not in line and not line.startswith('c '):
            lines.append(line)
    if not lines:
        return Verdict(None, None, None, seconds, proc.stdout,
                       outcome='error:no-output')
    if lines[0].startswith('UNSAT'):
        conflicts = int(lines[1]) if len(lines) > 1 else None
        return Verdict(False, None, conflicts, seconds, proc.stdout)
    conflicts = int(lines[1]) if len(lines) > 1 else None
    return Verdict(True, lines[0], conflicts, seconds, proc.stdout)
