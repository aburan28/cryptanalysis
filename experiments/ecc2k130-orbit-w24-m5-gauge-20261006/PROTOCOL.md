# Frozen first-leaf Frobenius gauge for orbit-closed W24/m5 SAT

## Hypothesis and controlled comparison

The [ungauged planted run](../ecc2k130-orbit-w24-m5-sat-20261006/RESULT.md)
has a satisfiable 142,303-variable XCNF, but CryptoMiniSat found no model
within 100,000 conflicts. This experiment asks whether fixing **only the
first leaf's Frobenius exponent to zero** lets the same solver recover an
otherwise hidden five-summand witness on the **same public point**. The
archived planted witness already has first exponent zero, so this is a
controlled search-space restriction, not a new or selected target.

`CONFIG.json` pins the exact parent commit, receipts, XCNF and witness hashes,
source curve, factor-base policy, solver binary, fixed point, and bounds.
The producer must reconstruct the parent's XCNF byte for byte, then add eight
negative unit clauses on `meta["exponents"][0]`. It must not constrain any
mask, other exponent, inverse witness, S3 intermediate, or fiber selector.
The variable count, existing clauses and XOR rows must remain identical;
only the CNF count may rise by eight. A known planted assignment checks
satisfiability of the gauged formula, but does not count as solver recovery.

Run the first unknown-witness solve with CryptoMiniSat 5.14.7, one thread,
seed zero, 100,000 conflicts, 30 seconds, and 4 GiB observed RSS. Freeze
the solver command and resource monitor in the run receipt. If this primary
solve is `INDETERMINATE`, run one preregistered deeper diagnostic on the
**identical gauged XCNF** at 2,000,000 conflicts and 600 seconds; preserve
both outcomes. Do not interpret a conflict-limited result as UNSAT. A solver
model must independently pass the XCNF verifier and full group replay,
including `[4]sum=Q`, before it counts as recovered. No ordinary target is
attempted unless the primary 100,000-conflict solve passes that gate.

The exact paired comparison is gauged versus ungauged on the same frozen
planted point, solver, seed, conflict and wall bounds, and host class. Report
formula size, status, conflicts, peak RSS, and exploratory wall time. A
single planted result says nothing about natural relation yield. Preserve
timeouts, OOMs, monitor failures, invalid models, and zero-yield cells.

## Ordinary-target implication

For any five-leaf decomposition on a Frobenius-stable base, applying the
inverse Frobenius power of its first leaf maps that leaf's exponent to zero.
Thus a complete gauged ordinary-target search must test all 131 conjugates
of the target in a fixed order and charge **every** failed attempt to that
one target. The four `[4]` fibers must be retained for each conjugate.
If the primary planted gate succeeds, attempt the one frozen ordinary point
from workload `eee7f6ee5f6b`, conjugates `0..130`, with the same 100,000
conflicts, 30-second and 4-GiB bound per conjugate; stop only on an
independently verified decomposition or after all 131 attempts. This is a
PDP diagnostic, not a complete DLP: inverse transport of relations, factor
logs, final rank/linear algebra, target descent, and matched rho remain
unmeasured. If the primary planted gate fails, ordinary costs and yield
remain `null`, rather than zero.

Save `/Volumes/SSD990/cryptanalysis/sage --runtime-info` before any measured
local job and launch Sage jobs through that checked repository launcher.
Record code and input hashes, exact raw output, source-bound certificates,
and excluded attempts. Host CPU isolation is unverified, so timing ratios
are exploratory. Keep `candidate_id: null` until a complete IC pipeline is
specified and measured. The decision is: promote the gauge only if the
primary unknown-witness solve independently passes; otherwise retain it as
a bounded negative or diagnostic result and prioritize a structurally
different PDP solver.
