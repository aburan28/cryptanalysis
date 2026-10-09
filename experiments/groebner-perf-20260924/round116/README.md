# Batched initial generator reduction in certified F4

The five hard 12-variable point-decomposition continuations spend
48.5–61.6% of deterministic F4 work normalizing the initial 26 matrix-seed
rows and 31 original equations one at a time. This opt-in experiment puts
eight or more initial rows through one proof-carrying Macaulay elimination
before starting the usual S-pair queue. Smaller inputs retain the original
serial path. The matrix starts with an empty basis, so it performs linear
row operations on exactly the supplied generators. Each matrix output is
then normalized against the incrementally installed basis. Replacing a
generator list with a row-echelon basis of the same GF(2) span preserves the
generated ideal. Each XOR remains a derivation node, and the normal F4
completion and final interreduction still run.

This transformation changes the proof trace and logical work counts.
Validation therefore compares the final reduced Boolean basis, assignment,
original-equation check, and curve replay with the frozen query, while an
independent native checker verifies the new derivation DAG, reverse ideal
membership, Buchberger pairs, and Boolean field pairs. The matrix and
continuation budgets remain shared and unchanged; any failure or cap stays
in the panel. The optimized and undefined-behavior-sanitized builds both
participate.

The build accepts only the source-matched reference engine SHA-256 in
`generate.py` and records source, compiler, architecture, and binary hashes.
Run it against an audited round112 reference:

```sh
python3 experiments/groebner-perf-20260924/round116/build.py \
  --reference-root /absolute/source-matched/reference
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round116/panel.py \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/batched-panel
```

Any local timing is a diagnostic. A controlled CPU gain needs matched
complete-query replay on an isolated host with the repository's required
receipt.
