# Exact S3 midpoint implications solve the N53 and N83 free-intermediate controls

Computing each fixed leaf pair's two exact S3 roots and constraining its
pair intermediate to those choices made the Q1419 balanced four-summand
`free_mids` controls **SAT in 2 conflicts at N53 and 3 at N83**. The
parent formulas reached their one-million-conflict caps with the same four
leaves and target selector fixed. The new method preserves every original
CNF and XOR row, adds two selector variables and `4n` binary clauses, and
lets SAT choose both intermediate roots. The [independent XCNF and group
audit](audit.json) passed both models. The returned leaves and signs match
the archived controls, whose independent [checked-Sage replay bridge](sage_bridge.json)
was revalidated through the repository launcher.

This is proposal `Q20261010131600`, with `candidate_id: null`, `run_id:
null`, and `isogeny: "none"` (`ISO0`). The [freeze](freeze.json) binds the
Q1419 target points, exact Q1301/Q1325 factor-base digests, parent formula
bytes, augmented formula bytes, solver binary, source, and caps. N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, actual `B=24062`, `K=227`.
N83 uses `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, actual `B=30977592`,
`K=186612`.

| Frozen control | Parent Q1419 result | Exact-root result | Oracle API calls | Added CNF / variables | Construction / oracle / solver wall, exploratory |
| --- | --- | --- | --- | ---: | ---: |
| N53 `free_mids` on archived ordinary point, witness leaves fixed | `censored`, 1,000,001 conflicts, 15.382 s | verified SAT, **2 conflicts**, 15.0 MiB peak child RSS | 2 inversions, 16 multiplications, 4 squarings, 54 Frobenius, 2 traces | 212 / 2 | 1.112 / 0.008 / 0.076 s |
| N83 `free_mids` on known-satisfiable control, witness leaves fixed | `censored`, 1,000,001 conflicts, 19.653 s | verified SAT, **3 conflicts**, 24.8 MiB peak child RSS | 2 inversions, 16 multiplications, 4 squarings, 84 Frobenius, 2 traces | 332 / 2 | 3.062 / 0.022 / 0.087 s |

The oracle interval is included in construction, so the three wall columns
are not additive. Solver wall includes process launch and formula loading;
decompression is recorded separately in each [run receipt](runs). The
operation counts cover the two root calls, not formula generation or the
solver. The host has no isolation receipt, so wall times are stage
diagnostics. The conflict counts establish that the added exact root
implications removed the free-intermediate search problem on these fixed
leaf controls; they do not rank complete ordinary-query solvers.

For nonzero `x,y`, the oracle solves

```text
(x+y)^2 z^2 + xy z + (xy)^2 + 1 = 0
```

with one field inversion per pair in the regular case and a binary-field
half-trace. The freeze records both roots for each pair. The auditor checks
that every root satisfies S3 and that the augmented formula consists of
the exact archived formula plus the stated implications. A selector encodes
either root for each midpoint; the archived witness root is only checked
after construction and is not pinned into SAT. The checked-Sage bridge
confirms that the returned raw leaves and signs are the independently
replayed archived witnesses.

## Next solver gate

Attach this exact root oracle during **free-leaf search** so midpoint
choices are constrained whenever a leaf pair becomes fixed, while charging
every failed branch and oracle call. First recover Q1419's one-leaf and
two-leaf controls without witness pins for those leaves, then an unpinned
ordinary N53 relation, followed by an ordinary N83 relation on the exact
Q1325 base. Pair those costs with the existing pair-table and root-index
stages on the same public points. The fixed-leaf controls do not measure
natural relation yield or novel rank; the complete N131 solve exponent
remains `null` until collection, matrix, descent, and replay are charged.
