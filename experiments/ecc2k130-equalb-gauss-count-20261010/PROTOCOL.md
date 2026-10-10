# Frozen Gaussian matrix-count gate on equal-B ECC2K-130 PDP

This gate compares two and five active CryptoMiniSat Gaussian matrices on the
same exact six-summand, four-lift ordinary query used in the [parent
gate](../ecc2k130-equalb-gauss-gate-20261010/RESULT.md). It holds the source
curve `EC1N131Ckb1h136f03e58c98`, public query index zero, target-lift
order, `B=11,743,888` usable factor-base points, balanced S3 tree, native-XOR
formulas, solver binary, and resource envelope fixed. The two formulas are
normal-weight-four with the exact four-threshold counter and source W24 with
its selected equal-size prefix. The query is an ordinary public point from
the [frozen input stream](../ecc2k130-normal4-equalb-m6-20261010/RESULT.md),
not a planted decomposition.

## Frozen inputs and policy

[`CONFIG.json`](CONFIG.json) binds parent commit
`66d6fa1fcca4d02b0216014b15f1c251c9879426`, the parent's configuration
and guarded-runner SHA-256, both compressed and raw formula hashes, the
checked CryptoMiniSat 5.14.7 binary SHA-256, the equal-B input-prefix hash,
and the exact four-cell order. The raw normal4 XCNF SHA-256 is
`21b4c7c292fd1441f127428927fb6cf6c51849e279d97e72adbbd95343048d79`;
the raw W24 XCNF SHA-256 is
`f71601554772d6805b364638bc25fce1a23c96b0df65f4b9fd8a2dedd5f45e3a`.
The input verifier decompresses each archived XCNF and rehashes its bytes
before launching a solver.

Both policies use one thread, `--maxmatrixrows=9000`,
`--maxmatrixcols=14000`, `--autodisablegauss=0`, `--maxtime=60`, an external
70-second wall guard, and a 4-GiB observed-RSS guard. Only
`--maxnummatrices` changes: five is the contemporaneous control and two is
the candidate. Run in the order normal4/five, normal4/two, W24/two,
W24/five. Save stdout, stderr, command, exit code, wall, RSS samples and
peak, source/binary/config hashes, restart rows, matrix dimensions and
elimination activity for every cell, including producer failures and caps.
The local host has no isolation receipt, so wall ratios are exploratory
solver-stage diagnostics. Input loading and formula checking are recorded
separately from solver wall.

## Decision and continuation

Independent transcript audit must establish that a solver entered search.
`BOUNDED_UNKNOWN` is a capped search, never UNSAT; a SAT model is unverified
until its six points, signs, selected target lift, projected relation, and
matrix row are replayed independently. Do not count a relation or a novel
rank row from solver status alone. Report paired peak-RSS ratio and active
matrix evidence by formula. The two-matrix policy retains the Gaussian
component if a matrix of at least 8,000 rows and 12,000 columns is admitted
and elimination calls are nonzero. A paired RSS ratio at most 0.70 in both
formulas is the predeclared memory gate. Conflicts and wall are diagnostics;
neither gate by itself promotes relation yield.

If both policies remain censored, freeze a longer single-query attempt as a
separate gate before opening the held-out 16/256-query prefixes. If any SAT
model passes independent curve and factor-base replay, preregister the
16-query pilot and 256-query yield screen on the same frozen stream, charging
every attempt and preserving rank novelty. Keep `candidate_id: null` until
relation collection, final matrix solving, and one-target descent are fixed.

Commit and open this protocol, configuration, runner, and audit before
running the four solver cells. Run `run_count.py --check` first; it performs
the hash and solver preflight without revealing outcomes. Preserve any
sandbox or RSS-probe failure as a distinct `PRODUCER_FAILURE` receipt and
freeze an explicit retry before running it.
