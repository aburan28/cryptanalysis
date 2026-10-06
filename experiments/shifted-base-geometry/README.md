# Frobenius-shifted factor bases: a concrete lead, not a full-width speedup

The useful lead from this audit is **assigning a different Frobenius-shifted
factor base to each summand**. An exact finite experiment confirms substantially
greater coverage of ordinary subgroup inputs with no increase in the folded
column count. It does not establish faster point decomposition, useful rank
collection, or an ECC2K-130 solving speedup.

The [2026-09-24 cost follow-up](FOLLOWUP.md) now includes a chained-S3 SAT
smoke and three IC-boundary-autolab runs. Both SAT variants timed out on every
smoke query at the declared budget. No new crossover or full-width speedup
was established; the coverage measurements below remain geometry evidence.

This is a known construction, not a novel algorithm: Galbraith, Granger, Merz
and Petit, [On Index Calculus Algorithms for Subfield Curves, section 3.1 and
Theorem 3.2](https://pure-oai.bham.ac.uk/ws/files/104974339/On_Index_Calculus_Algorithms_for_Subfield_Curves.pdf).
Their conditional relation-collection saving is m! when decomposition costs
are equal. Section 3.2's invariant-base construction is a separate mechanism.
Neither theorem establishes that index calculus beats rho on ECC2K-130.

## What was checked locally

The existing Hamming-weight encoder in `ecc2k130/codegen/decomp.py` gives every
summand the same invariant base. The existing polynomial-basis experiment in
`experiments/pdp-scaling/descend.py` similarly uses the same block polynomial
table for every summand. Neither inspected path uses a distinct subspace per
summand. This is a scoped source inspection, not a claim that no related code
exists anywhere in either repository.

The paragraph explaining m! in `crypto/RESEARCH_KOBLITZ_INDEX_CALCULUS.md`,
under "Where the speed-up lives", conflates the two constructions by assuming
the shifted bases coincide. Removing redundant tuple permutations from a
fixed sumset and enlarging coverage through distinct bases have different
effects. The invariant-base unit test here confirms that merely relabelling
one invariant base does not increase its sumset support.

The degree-131 feasibility ledger in `experiments/factor-base-yield-v2`
admits zero full-width candidates. Its rank-aware pair scan reduced aggregate
collection time by 1.844%, with mixed per-base results and no paired confidence
interval. Existing F5 and SAT measurements do not supply the missing cost of
the shifted-base polynomial systems.

## Exact finite experiment

`audit.py` is a forward sumset geometry instrument restricted to fixed toy
degrees 13 and 19. It has no target input, inverse decomposition lookup,
unknown-logarithm extraction, or cloud execution. It enumerates all outputs
of the declared tuple domains and reports support and multiplicity.

For each of eight seeds and each of three parameter cells, it finds a normal
basis, constructs interleaved coordinate subspaces of dimension three, lifts
all their abscissae, and retains exactly the points in the prime subgroup.
The subspaces intersect only at zero; the associated nonidentity point bases
are disjoint. Both signs are retained. Subgroup filtering is performed without
cofactor clearing the candidate points, so their abscissae do not change.

The comparison is between sums of m points from one base and sums taking one
point from each of its m Frobenius shifts. The first domain uses unordered
multisets with repetition; the second uses a Cartesian product. These are
deliberately different mathematical domains. Both resulting supports are
measured under the same uniform nonidentity subgroup-input law.

The full shifted union folds to exactly the same signed Frobenius columns as
the first base. Every shifted point's scalar transport is checked. Existing
public generator-trace information is recorded; no useful rank is attributed
to the resulting supports.

| Degree | Summands | Nonempty / total cells | Observed coverage ratio among nonempty cells |
| --- | ---: | ---: | ---: |
| 13 | 4 | 6 / 8 | 4.00–11.76× |
| 19 | 5 | 4 / 8 | 5.33–51.78× |
| 19 | 6 | 4 / 8 | 10.67–73.46× |

All ten empty-base cells are retained with null ratios. These ranges describe
this finite panel; they are not confidence intervals, asymptotic estimates,
or a prediction at degree 131. Degree-19 base sizes for the eight seeds were
inspected before running the complete panel; no cells were removed. There is
no claimed held-out prediction.

Two concrete examples in `results.json`:

- Degree 19, five summands, seed 87008: six actual base points, two folded
  columns, support 146 -> 7,560 out of 130,872 ordinary nonidentity inputs.
  Exact coverage ratio: 51.7808×. The tuple domains contain 252 and 7,776 leaves.
- Degree 19, six summands, seed 87007: four actual base points, one folded
  column, support 48 -> 3,526 out of 130,872 inputs. Exact coverage ratio:
  73.4583×. The tuple domains contain 84 and 4,096 leaves.

Those very small column counts are an important limitation. These examples
say nothing about the late-rank behavior of a large relation matrix.

Every complete histogram was replayed with separate convolution/long-division
field multiplication, exponentiation inversion, and flat tuple enumeration.
The measured path uses the existing toy engine's arithmetic and recursive
prefix reuse. All 24 comparisons matched exactly, including multiplicities
and identity outputs. This is project-authored replay, not external reproduction.
Base construction and source imports are shared; they are not independently
reimplemented by the histogram replay.

## Why this is not yet a runtime result

The larger domain also costs more to enumerate. In the saved single-run
diagnostic, the five-summand example took roughly 4.86 ms to enumerate the
old domain and 117.24 ms for the shifted domain; the six-summand example took
2.19 ms and 62.02 ms. These are instrumented stage timings, not repeated,
matched end-to-end benchmarks. Geometry gains cannot be relabelled as wall
speedups.

For any fixed row space and fixed query policy, let p_cov be ordinary coverage,
p_solve the conditional completion probability, and p_new the conditional
probability of a novel row among completed decompositions. Let c be mean
attempt cost, including failed attempts. Then the expected query-stage cost
per new row is

    c / (p_cov * p_solve * p_new).

This identity is local to a fixed row space and policy; matrix evolution,
construction, amortized preprocessing, final linear algebra and verification
must also be charged for an end-to-end comparison. The audit measures p_cov
only. It does not measure p_solve, p_new or c for an algebraic solver.

## The degree-131 constraints

The field degree is 131, while the subgroup has a 130-bit order. They must not
be interchanged in subspace or probability formulas.

The elementary normal-basis construction used here requires m*d <= 131:

| Summands m | Maximum subspace dimension d | Conditional m! factor | Bits represented by m! |
| --- | ---: | ---: | ---: |
| 4 | 32 | 24 | 4.585 |
| 5 | 26 | 120 | 6.907 |
| 6 | 21 | 720 | 9.492 |

Consequently the older m=5,d=28 and m=6,d=24 illustrative parameter rows
cannot simply inherit this construction's factorial saving. The coverage,
actual subgroup-filtered base cardinality, column count and polynomial
solving cost must be recomputed at admissible dimensions. The dimension
constraint is specific to this direct-sum construction, not a theorem ruling
out every collection of pairwise-disjoint subspaces.

The absence of small Frobenius-invariant linear subspaces is a different
obstruction. Direct modular checks give ord_131(2)=130. In characteristic two,
X^131-1 therefore has irreducible factor degrees 1 and 130, is squarefree,
and its invariant subspace dimensions are 0, 1, 130 and 131. This excludes a
small invariant linear base, but does not exclude the distinct shifted bases
in this audit. It also does not prohibit nonlinear invariant sets.

Do not multiply the 131-fold invariant-base saving and the 720-fold
shifted-base saving without a construction and cost analysis that realizes
both. Nor can extra Frobenius images of one folded equation count as fresh
rank: scalar multiples of a row remain dependent.

## Decision

**Retain this as a specific algebraic-solver research candidate. No dramatic
ECC2K-130 runtime improvement has been established.** The novel work here is
the repository-specific distinction and finite audit, not the published
construction itself.

The decisive next measurement would compare same-base and shifted-base
polynomial formulations on matched ordinary toy input streams. It must
include unsatisfiable inputs, construction, solver timeouts, verified
subgroup membership and novel rank, and report cost per useful row. A
coverage increase is useful only if additional solving cost and rank losses
do not consume it. An elementary enumeration implementation is not evidence
that a full-width implicit solver will scale.

## Reproduction

The geometry audit and arithmetic tests require Python 3.9 or newer and only
the standard library. The bounded SAT smoke and the fully assigned circuit
test additionally use `pycryptosat==5.14.7`; the circuit test is skipped when
that optional binding is unavailable. The recorded run used Python 3.14.

This change includes the five exact dependency files named in the saved
source hashes: `experiments/factor-base-yield-v2/engine.py` and `study.py`,
`toy_group.py`, `verify.py`, and `reference_group.py` under
`experiments/factor-base-yield/run-002/sources/`. These are unchanged library
snapshots from the earlier toy audit, included so a clean checkout can run
this experiment. Their original standalone command-line workflows require
additional artifacts from that earlier study and are outside this package.

From the repository root:

```sh
python3 -m unittest discover -s experiments/shifted-base-geometry -p 'test_*.py' -v
python3 experiments/shifted-base-geometry/audit.py \
  --independent-replay --out /tmp/shifted-base-geometry-replay.json
```

The output path must be new. The receipt records source hashes, every cell,
stage timings and operation counts. The complete panel took 2.34 seconds in
the saved run, including independent histogram replay and setup. Full-width
speedup, solver cost and useful-rank yield are explicitly null.
