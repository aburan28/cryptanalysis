# Q20261010191700: N53 weight-five matched million-conflict cell

Use Q20261010191500's exact ordinary XCNF, public point, and solver binary.
Set one thread, seed zero, default polarity/restarts, one million conflicts,
and 1,200 seconds external wall cap. Preserve the solver streams and child
resource receipt. If the solver returns SAT, the independent auditor must
replay the serialized XCNF and signed group relation. Compare this cell to
Q20261010183500's weight-four million-conflict cell only as capped solver
diagnostics on the same public point, not a CPU speedup claim.

Run `python3 runner.py freeze`, `python3 runner.py run`, and
`python3 audit.py`. Outputs refuse overwrite.
