# Native linearized norm builds the full W15 seed-bucket certificate

The exact degree-32,768 pair-output polynomial for one N131 W15 seed bucket
now builds in a **9.219 ms native interval** with **1,703,936 bytes** of
native peak RSS. Its 486 nonzero coefficients match the previously archived
checked-Sage polynomial **term for term**, including dense coefficient
SHA-256 `b2c472e1ce8187de33413c48eee469d1689f7a185b5f7d9932eca2c6ce7d1aad`.
An independent integer-field evaluator confirms zero at the archived raw-pair
output and nonzero values at both frozen field controls. This makes exact
whole-product-bucket constraints inexpensive to construct on demand; the
next method gate is using them to reject target-incompatible *pairs* of
buckets before enumerating source masks.

The exact field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is
`W15=span(t,…,t¹⁵)` and this frozen case uses mask-XOR seed `13686`, the
same seed and unrotated reciprocal pair-output coordinate as the
[Sage certificate](../n131_w15_pair_bucket_polynomial_20261010/RESULT.md).
It is a reusable algebraic construction stage with `target_count: 0` and
`candidate_id: null`.

For fixed seed `s`, the product image
`V_s={w²+sw:w∈W15}` has dimension 14. Every raw pair output reciprocal
coordinate `c` satisfies

```text
g_p(c) = c²+s²+(cp)²+cp = 0,       p∈V_s.
F_s(c) = ∏_{p∈V_s} g_p(c).
```

The native builder represents the linearized norm
`L_i(Y)=∏_{p∈V_i}(Y+(cp)²+cp)` using only the coefficient polynomials of
its Frobenius powers of `Y`. When adjoining a product-space basis vector
`v_i`, it computes `u_i=L_i((cv_i)²+cv_i)` and applies the exact identity

```text
L_{i+1}(Y) = L_i(Y)² + u_i L_i(Y).
```

The implementation stores polynomial coefficients as sparse exponent maps.
Squaring doubles exponents and squares field coefficients; evaluating
`u_i` shifts each exponent by two known Frobenius powers. The final
substitution `Y=c²+s²` has only two monomials per Frobenius power. The
largest intermediate coefficient collection in this run held **575
nonzero terms**, and the final polynomial held 486. The identity proves
equality to the full 16,384-product norm; the termwise comparison supplies
an independent representation check against the archived Sage construction.

| Frozen seed 13686 construction | Archived checked Sage v3 | Native sparse recurrence |
| --- | ---: | ---: |
| Product-image dimension / norm degree | 14 / 32,768 | 14 / 32,768 |
| Final nonzero coefficients | 486 | **486, identical values** |
| Construction-stage elapsed | 68.279 s | **0.009219 s** |
| Complete parent elapsed | 73.612 s | **0.064313 s** |
| Peak process RSS | 2,761,736,192 B, sampled Sage process | **1,703,936 B, native `getrusage`** |
| Positive / two field controls | zero / nonzero, nonzero | **zero / nonzero, nonzero** |

The [native protocol](protocol.json) froze source and binary hashes,
archived inputs, compiler, seed, one worker, 150-second parent cap, and
4-GiB RSS cap before the completed run. The [run receipt](result.json),
[raw output](run.stdout.txt), and [coefficients](coefficients.tsv) retain
the native rounds and exact output. The [independent audit](audit_result.json)
parses every coefficient, recomputes the dense digest, and evaluates the
three field controls using a separate bit-polynomial multiplier; its
[audit protocol](audit_protocol.json) binds all inputs before replay.
The native and Sage timings use different implementations and RSS sampling
methods on an unisolated host, so they are exploratory construction-stage
observations. Exact coefficient equality, final term count, and degree are
deterministic results. The output is only 23 KiB on disk, so the certificate
can be saved or recomputed without the Sage process's memory footprint.

The first parent monitor attempted a `ps` RSS sample that this sandbox
denied before a result was written. Its [frozen v1 protocol](protocol_v1.json),
[source](run_v1.py), empty logs, and [failure receipt](failure_v1.json)
preserve `PRODUCER_FAILURE_PARENT_MONITOR_PS_PERMISSION`. Version two uses
the native process's own peak RSS and round-level cap checks, with a parent
wall watchdog. Both versions leave the mathematical source and binary
unchanged.

## Next target-coupled gate

Use the same sparse norm construction for the **pair buckets in both**
four-atom blocks of the W15 eight-offset policy. Compose the pair-output
constraints with the within-block and public-target S3 links while both
block outputs and at least one free pair remain symbolic. First test exact
whole-bucket rejection and source
replay on the frozen N41 public point, with all seeds and masks unpinned;
count candidate buckets, rejected buckets, surviving output coordinates,
group witnesses, verified relations, novel rank, complete wall, and RSS.
The [native mixed-S3 inverse](../n131_mixed_s3_stream64_20261010/RESULT.md)
is the stronger existing kernel for a *proposed* four-atom output; this
polynomial supplies a compact constraint for generating or rejecting whole
families before that inverse runs. Require a source-bound N131 work and
memory projection within one worker, 600 seconds, and 4 GiB before the
published-point query. Factor-base logs, fresh target recovery, and the
matched one-target rho comparison follow that ordinary-relation gate.
