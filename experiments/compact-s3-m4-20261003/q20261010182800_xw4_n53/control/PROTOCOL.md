# Q20261010184800: known-decomposition control for N53 x-weight four

Pin Q1410's archived four-leaf witness, its two pair-sum x coordinates,
and its raw-target-preimage selector inside Q20261010183500's exact
weight-four balanced S3 formula. The witness belongs to the weight-three
prefix of the complete weight-four factor base. Freeze all source/input
digests first, append only unit clauses to the ordinary formula, and run
the same CryptoMiniSat binary with one thread, seed zero, a 100,000-conflict
limit, and a 60-second external wall cap. Independently check the SAT
model, signed group relation, cofactor projection, and exact base keys.

This is a correctness control on a known decomposition, not an ordinary
relation-yield estimate. Commands: `python3 control.py freeze`,
`python3 control.py prepare`, `python3 control.py solve`,
`python3 audit.py`. Outputs refuse overwrite.
