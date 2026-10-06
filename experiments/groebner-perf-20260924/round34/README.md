# Bounded affine contradiction certificates

This experimental path extends round33's exact Boolean quadratic-residual
solver with independently checked identities whose equation multipliers have
degree at most one. It targets the residual enumeration that becomes expensive
on the frozen 24- and 27-variable public-point queries. It is not a general
F4/F5 replacement or an asymptotic improvement claim.

For each fixed-block assignment, the producer first performs the existing
quadratic linearization. An inconsistent linearization retains its unchanged
constant equation-combination certificate. If the lifted nullspace is cheaper
than the original residual space, the producer searches it first and attempts
an affine certificate only when that search finds no actual root. Otherwise it
attempts the certificate before enumerating the original residual variables.

The extra certificate is an exact identity in the Boolean quotient:

`sum_j u_j(y) F_j(y) = 1`, with `degree(u_j) <= 1`.

The producer forms rows `(1, y_0, ..., y_(r-1)) * F_j`, reduces Boolean cubic
monomials, and tracks the equation/multiplier combinations. The separate
checker rebuilds coefficients from the original packed ANF and expands each
identity with numeric monomial masks. It shares neither the producer's
elimination state nor its cubic-column layout. Every remaining branch is
exhausted over its **original** residual assignments. Exact root count,
distinct checked roots, the Boolean staircase, minimal leading terms, and
standard tails certify the complete reduced basis, as in round32.

The wire format keeps the round33 `branches * ceil(equations/64)` constant
prefix, then appends sorted, nonoverlapping records:

`[branch, u_0 limbs, u_1 limbs, ..., u_r limbs]`.

Dimensions, extent, padding, unique ascending branch IDs, constant-proof
overlap, and every identity are checked. Zero witnesses prove nothing. The
public query still includes fresh packed descent, proof generation/copy/hash,
independent certification, original-equation checks, and full public-point
curve replay. Setup and extra offline auditing remain separate. No query
answer is cached.

## Bounds and honest baselines

- Multiplier work: 67,108,864 row insertions plus pivot-row XORs per query;
  at most 65,536 per attempted branch. Logical 64-bit XOR counts are separate.
- Proof storage: at most 64 MiB; capacity growth is explicit and accounted.
- Existing exact enumeration: 4,194,304 assignments; at most 256 complete roots.
- Basis proof: 1,000,000 work units; each specialization table: at most 64 MiB.
- Unsupported or exhausted cases remain explicit failures. Partial roots and
  partial certificates are never returned as an answer. Failed native calls
  preserve diagnostic work counters, and their full wall time is charged.

The wide paired baseline compiles **unchanged round33 native source** with
both its producer and checker enumeration bounds expanded to 134,217,728.
`expanded_baseline.py` only redirects round33 bindings to those libraries.
This allows the previous exact algorithm to finish the same 27-variable
inputs. Its flags, sources and binary hashes are retained and audited. Small
queries additionally compare the existing sparse, quadratic, constant-proof,
and narrow-coefficient implementations. The baseline is explicit; it is not
a claim to have paired every solver in the world.

The initial 33,554,432-work prototype exhausted its multiplier budget on the
first 27-variable control, then exhausted exact enumeration. It was retained
as an inconclusive attempt before the final 67,108,864-work budget was frozen.
This is a bounded filter, not a complete refutation method: the tests retain
an inconsistent four-variable system with an independently checked dual
witness proving that no degree-one multiplier identity exists. That system
requires the exact enumeration fallback.

## Reproduction

Use a normal Python interpreter; these programs do not import Sage.

```sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python experiments/groebner-perf-20260924/round31/build.py
python experiments/groebner-perf-20260924/round32/build.py
python experiments/groebner-perf-20260924/round33/build.py
python experiments/groebner-perf-20260924/round34/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round34 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round34/measure_multipliers.py --correctness-only --repetitions 2 --output correctness.json.gz
python experiments/groebner-perf-20260924/round34/measure_multipliers.py --correctness-only --large-controls --repetitions 2 --output wide-correctness.json.gz
python experiments/groebner-perf-20260924/round34/audit_multipliers.py wide-correctness.json.gz
```

For macOS Metal, append `--metal` to builds for rounds31–34 and to measurement
commands; set `QUADRATIC_TEST_METAL=1` for tests. Optional Metal still accelerates
only the existing constant linearization for at most 31 quadratic features
and 32 equations. The affine stage is CPU code. In particular, 24/27-variable
requested Metal queries record **CPU shape fallback**, not GPU execution.
CPU remains the default. Neither CUDA nor other GPU compatibility is claimed.

The offline Python auditor verifies the original inputs, identities, complete
root sets, exact producer work, proof capacity, coefficient widths, source and
binary bindings, timing boundaries, fallback/device use, and full curve
witnesses. Up to 24 variables it additionally compares unchanged full-space
truth enumeration. At 27 variables it proves rejected branches directly from
the identities and exhausts all uncertified original assignments. Its cache
is keyed by complete immutable inputs/proofs and is used only outside timing.
CI rebuilds native code on Linux and macOS and audits fresh and retained data.

For performance attempts, omit `--correctness-only`. The unchanged admission
gate requires one-minute load at most one per logical CPU initially, at every
paired group boundary, and finally. Small trials predeclare 31 measured paired
repetitions plus one warmup; wide trials predeclare seven plus one warmup.
Repeat each trial independently. All arms use the same frozen input and are
randomized within a repetition. The wide controls are three distinct seeds
at each of 21, 24 and 27 variables. Bootstrap intervals describe paired timing
variation on these controls, not unseen inputs or asymptotic complexity.
In audit summaries, the small-control `wins` field compares against sparse;
the wide comparison is explicitly `expanded_cpu_over_multiplier_cpu`.
A nonadmitted attempt contains no timed queries; interrupted, failed and
unqualified runs remain evidence and never count as wins.

## Research scope and next experiment

Low-degree Macaulay contradiction certificates and hybrid specialization
are established ideas, including the crossbred/BooleanSolve literature:
[Joux–Vitse, 2017](https://eprint.iacr.org/2017/372.pdf) and
[Bardet et al., BooleanSolve](https://arxiv.org/abs/1112.6263).
The contribution here is a bounded implementation, independent certificate
checking, packed transport, and measured applicability to these exact inputs.
The research literature's distribution and regularity assumptions have not
been established for these structured fixtures.

The next GPU hypothesis is to parallelize the many independent residual
proof systems **within one query**, first extending constant elimination to
36/45/55 features and then testing batched cubic row elimination. It needs a
portable CPU fallback, bounded proof output, independent checking, and full
query timings including transfer and synchronization. Coordinate-block
symmetry is another concrete hypothesis, with orbit handling and proof
transport still to be implemented and validated. Neither hypothesis is an
implemented F6 algorithm or a proven asymptotic improvement.

These are planted PDP correctness and component-performance controls.
`candidate_id`, full `IC_online_ms`, and paired `rho_online_ms` remain null.
Natural relation yield and complete same-point single-target IC/rho recovery
require separate candidate manifests and end-to-end measurements. Do not
multiply these component ratios into an IC speedup.
