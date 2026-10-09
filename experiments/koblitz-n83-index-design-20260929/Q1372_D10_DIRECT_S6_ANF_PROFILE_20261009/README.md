# Q1372: direct S6 Boolean ANF profile on N83

**Result:** the frozen five-point S6 relation is correct under an independent
Sage evaluation, and the direct seed-substituted expansion reaches a dense
intermediate at its first nontrivial symmetric term. The checked profile
stopped at the declared 100,000-field-monomial cap before building the final
S6 coordinate equations or invoking a solver.

## Frozen control and encoding

The profile uses curve
`EC1N83Ckb1h876c2921cb64`, the exact Q1104 d10 seed subspace, and Q1105 control
`d10-c000`. The exact seed domain contains 493 usable masks among the 1,023
nonzero ten-bit masks. Five ten-bit blocks give 50 Boolean seed variables;
each block has one exact valid-mask equation. Their ANFs each contain 521
terms of degree at most 10.

The raw cofactor-preimage target is the unprojected group sum from Q1105. Each
planted term's applied shift is the sum modulo 83 of its Q1104 canonical shift
and Q1105 query shift: `[43, 24, 43, 82, 80]`. The planted masks are used only
for the numerical control audit. They are not inserted into the substituted
equations. The equation system is built from the complete exact seed-mask
truth table and those frozen shifts.

## Profile

The five target-independent `u=(x+1)^-1` seed functions each have 983 field-
valued ANF terms. The five `w=u^2+u` functions also each have 983 terms.
The direct system has 83 S6 coordinate equations in addition to the five
valid-mask equations, but its expanded equation profile is incomplete.

The profile hit its cap while forming `e2` at `elementary_e2_step2`. It had
already materialized 114,688 distinct field monomials for the first cross
product `w_0 w_1`; the next cap check stopped construction. The peak process
RSS was 340,361,216 bytes. The measured ANF build stage took 7.080 seconds on
the recorded local host, including reconstruction of the exact valid domain
and seed tables. Sage startup and the required runtime check are outside that
stage timing.

The separate [`e2_support_count.json`](e2_support_count.json) records the
structural count implied by the measured ANFs. Since each seed block has
disjoint variables and each `w_i` has no constant monomial, each of the ten
unknown-unknown products contributes `983^2 = 966,289` distinct field
monomials. The five products with the fixed nonzero target `w` contribute
another 4,915. Thus the complete `e2` intermediate has 9,667,805 distinct
field monomials under this encoding. This count is derived from the frozen
support structure; the full intermediate was not materialized.

Q1117's chained S3 control built 6,232,734 Boolean-polynomial terms across
337 equations in 299 variables, then reached its recorded 180-second
PolyBoRi timeout. Q1372 reduces the variable count to 50 but reaches the
large `e2` intermediate before final S6 expansion. These records compare
solver representations at their measured construction stages; final equation
term counts and Gröbner solve cost remain unmeasured.

## Correctness and provenance

The initial Q1372 attempt used only the Q1105 query shifts and omitted the
Q1104 canonical shifts. Its numeric S6 check was nonzero, so that attempt is
retained as an implementation-error record and excluded from the profile
conclusion. Retry 1 applied the combined shifts and passed the internal
numeric check. Retry 2 contains the detailed capped profile and was replayed
independently by Sage; the replay returned S6 value zero. The prior
independent Q1105 group replay also passes for all planted controls, including
`d10-c000`.

Run records and runtime receipts are in
[`runs/`](runs/). The profile command uses the repository launcher:

```sh
Q1372_RUN_DIR=/absolute/path/to/runs/q1372_d10_c000_direct_s6_anf_profile_retry2_20261009 \
  /Volumes/SSD990/cryptanalysis/sage -python profile_direct_s6_anf.py
```

All proposal-stage records retain `candidate_id`, `workload_id`, and `run_id`
as `null`. This run records a planted formula check and ANF construction cost;
ordinary-query relation yield belongs to the subsequent N83 gate.

## Next experiment

The full direct S6 ANF route should remain behind a factorized or block-sparse
representation. The measured `e2` support already reaches 9.67 million field
monomials before the higher S6 terms. Continue the N83 scaling gate with the
wide-key common-root index and ordinary-query yield measurements, under a
fresh disk preflight; preserve the planted controls as correctness checks.
Only a complete, replay-verified one-target DLP can advance the comparison to
ECC2K-130.
