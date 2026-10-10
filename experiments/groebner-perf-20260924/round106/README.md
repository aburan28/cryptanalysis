# Minimal-row Macaulay back substitution

This opt-in CPU experiment selects the minimal leading rows of a fresh Boolean
Macaulay echelon matrix before backward elimination. It reduces only those
rows, using later pivots from left to right. The reference fully reduces every
pivot row before selecting the same outputs. The forward elimination, compact
input, independent quotient-map checker, proof transport and complete-query
timing boundary remain unchanged.

Run `python round106/run_validation.py --output PATH --diagnostics` from this
experiment's parent directory. The runner requires a clean committed source
freeze, builds optimized and UBSan libraries, runs unit and frozen controls,
independently audits their proofs and work counters, rejects corrupted
artifacts, and optionally records the entire diagnostic panel. It retains a
failed attempt and never selectively retries timing cells.

See [RESULTS.md](RESULTS.md) for the frozen observations and retained failures.
See [PROTOCOL.md](PROTOCOL.md) for the equivalence argument, limits and frozen
comparison. This is a Macaulay component study, not a complete IC pipeline or
a new F6 asymptotic result. CPU timing ratios remain unknown without the
repository's physical-host isolation evidence. GPU execution is unchanged.
