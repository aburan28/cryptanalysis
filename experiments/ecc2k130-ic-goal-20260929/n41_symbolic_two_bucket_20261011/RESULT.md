# Symbolic two-bucket elimination and its complete-scan boundary

A division-free linearized recurrence now tests **two still-free N41 pair-output
families** against a target lift without enumerating either family's output
coordinates or pair-state vector. At left seed 16 and right seed 5, it gives a
degree-one GCD on positive raw target lift 3; independent checked Sage replay
recovers the exact raw group sum and its previously audited projected pair
witness. The same frozen two-seed panel has degree zero on the other seven
positive/negative raw lifts. The unrestricted 63-by-63 seed-family scan hit
its first 120-second raw-lift cap after 693 of 3,969 pairs, which fixes a
quantitative boundary for this implementation and keeps the complete scan
`CENSORED_TIME`.

The [protocol](protocol.json) fixes `GF(2)[t]/(t^41+t³+1)`, the Koblitz model
`y²+xy=x³+1`, curve `EC1N41Ckb1h7d5e80d3c4d0`, W6 rotations 20 and 30,
actual **B=256**, folded **K=26**, one worker, 120 seconds per raw lift, and
4 GiB process RSS. Its inputs are the frozen positive and negative projected
residuals, each with four exact raw preimages. No pair output or source mask
is pinned in the complete-scan producer. The positive seed-pair control is
explicitly supplied in the separate profile. This is proposal
`Q20261011232500`; `candidate_id`, `run_id`, and target count remain null.

## Exact family operator

For nonzero right seed `s`, the product image
`V_s={w_a²+w_s w_a}` has dimension five. At symbolic left coordinate `Z`
and fixed target reciprocal `t`, the 32 quadratic resultants are
`q(p)=A(Z)+B(Z)p+E(Z)p²`, for `p∈V_s`, with `A,B,E` defined in the preceding
[linearized-bucket identity](../n41_linearized_bucket_composition_20261011/RESULT.md).
The map `p↦B(Z)p+E(Z)p²` is additive over `GF(2)`. Starting with its five
basis images and the target value `A(Z)`, repeatedly apply

`L_{i+1}(X)=L_i(X)²+L_i(v_i)L_i(X)`.

Fifteen polynomial square-and-multiply updates produce the **exact**
degree-128 right-bucket norm, without constructing 32 factor resultants.
The left seed has its own compact degree-at-most-64 polynomial `F_s'(Z)`.
`gcd(norm,F_s')` rejects or retains the entire left/right seed-family pair
while both pair-output coordinates remain unchosen. The operation is
division-free until the final polynomial GCD and remains valid when an
intermediate transformed basis loses rank.

The [frozen profile](profile.json) compared the compact norm to the
independent 32-factor product as a **full polynomial identity** for right
seeds 5 and 17 on all eight raw target lifts: 16 exact equalities passed.
It then tested left seed 16 by GCD. Exactly one of those 16 seed-pair
decisions hit: positive lift 3, right seed 5, GCD degree one. The
[independent Sage audit](audit.json) rebuilt the left and right product
polynomials separately, reproduced all eight right-seed-5 GCD decisions,
extracted left reciprocal `585190544792` and right reciprocal
`1979731517413`, and verified that their lifted points sum to the raw
target. Multiplication by four gives the same two projected pair points as
the earlier independently audited bucket witness. The profile's local
148.419 ms positive control includes direct-product validation and is an
exploratory component interval, not a standalone optimized query.

| Frozen run boundary | Exact record |
| --- | ---: |
| Supplied-seed full-polynomial controls | 16/16 equalities |
| Independent direct-GCD raw-lift controls | 8/8 decisions |
| Unrestricted first raw lift, seed pairs completed | **693/3,969** |
| Completed right seed families | **11/63** |
| First raw-lift wall/status | **125.934 s / `CENSORED_TIME`** |
| First raw-lift bucket hits in covered prefix | 0 |
| Positive supplied-seed group witness | exact raw sum and fourfold projection |

The first raw lift's 125.934 seconds includes a right-family completion
past the 120-second check; it is retained at its observed wall rather than
presented as cap compliant. After that censored option, the identified
producer was stopped with SIGTERM, exit 143, to avoid seven more capped
options. The [interruption receipt](interruption.json) binds its one-line
[stdout](run.stdout.txt), empty stderr, frozen protocol, source, and the
absence of a complete `result.json`. The [archive verifier](verify.py)
checks all hashes, exact profile/audit decisions, and the partial-scan
classification. The first Sage audit attempt aborted inside native
polynomial root factoring, exit 134, before writing an audit; its
[failure receipt](audit_failure_v1.json) and [source](audit_v1.py) are
retained. The passing audit instead solves the right quadratics by the
odd-degree half-trace and extracts the degree-one left root directly.

## Degree-131 work gate

Under the corresponding W14 polynomial-source policy, each right seed
requires a rank-13 recurrence of **91** polynomial updates. A right norm
has degree at most 32,768, and each compact left bucket degree at most
16,384. Testing every nonzero left/right seed pair takes
`(2^14−1)² = 268,402,689` GCD decisions **per raw target lift**. Even with
free norm construction, one lift needs at least 447,338 decisions per
second to finish in 600 seconds; all four raw lifts need at least
1,789,352 per second. The corresponding W18 seed-pair Cartesian is
68,718,952,449 pairs per lift. These are exact source-bound decision counts,
not measured full-width rates. The N41 producer's partial 693 decisions
over 125.934 seconds are an unisolated implementation diagnostic and do not
form a scaling law.

The recurrence supplies an exact family-level target predicate, but a
complete Cartesian seed sweep does not meet even the N41 stage cap here.
The next algorithm must **select or eliminate many seed families jointly**
from the public target before paying per-pair GCD work, or use a different
point-decomposition geometry. Its first acceptance test remains an unpinned
N41 eight-point row within 120 seconds and 4 GiB, followed by a credible
N131 work/RSS projection, ordinary relation yield and useful rank, factor
logs, and a fresh single-target online IC/rho comparison.
