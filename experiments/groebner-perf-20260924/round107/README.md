# Bounded parity witnesses for Boolean Macaulay outputs

This opt-in experiment compresses the retained derivation graph after the
round106 minimal-row producer finishes ordinary proof pruning. Each retained
output is expressed as a parity sum of original input equations times layout
monomials. The basis coefficients, forward elimination, backward elimination,
independent checker and complete-query boundary remain unchanged.

Run `python round107/run_validation.py --output PATH --diagnostics` from this
experiment's parent directory. The runner requires a committed source freeze,
builds optimized and UBSan libraries, checks bounded prefixes and proof
semantics, runs the frozen controls, rejects corrupted artifacts, and records
the full diagnostic panel only after correctness passes.

See [RESULTS.md](RESULTS.md) for the full frozen observations, including regressions.
See [PROTOCOL.md](PROTOCOL.md) for the algebraic argument and resource contract.
This is a proof-representation experiment. It does not establish a new general
Gröbner algorithm, GPU benefit, world-fastest F4/F5 result or IC/rho speedup.
CPU timing ratios remain unknown without physical-host isolation evidence.
