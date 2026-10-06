# High-regularity, GPU, and “F6” research direction

The next iteration is documented in [round2/README.md](round2/README.md), with a complete batched GPU RREF prototype, an exact evaluation/interpolation solver, stronger basis certificates, and further measurements.

“F6” is a working research label. No new proved algorithm or reduced complexity
bound is claimed. The immediate objective is verified experiment throughput
on the actual polynomial-system families, followed by broader competition.

## What the review suggests

Faster elimination is useful, but building fewer rows and avoiding repeated
symbolic work can win before arithmetic starts. This campaign's prime-field
symbolic fix removes roughly half the rows in one fixture without changing
the column count. The Boolean speedups similarly remove preprocessing work.
Neither changes the measured degree of regularity; this campaign has not yet
measured that degree on a demanding scaling panel.

At degree D, ordinary dense monomials up to D number binomial(n+D,D). In a
Boolean quotient they number sum_{j=0}^{min(n,D)} binomial(n,j). High regularity
therefore creates a combinatorial matrix-size barrier. Faster hardware changes
the cost per row operation; avoiding degree growth or reusing a factorization
can change the amount of work. No general method for eliminating this barrier
has been established by our experiments.

## Existing work to build upon

- [M4GB, authors' implementation and paper](https://github.com/cr-marcstevens/m4gb)
  retains tail-reduced multiples and reduces repeated work on reducible
  monomials. This directly motivates replacing our eager full-universe tables.
- [M5GB](https://arxiv.org/abs/2208.00844) already combines tail-reduced reducers
  with signature criteria and supplies correctness/termination arguments. The
  combination “F5 plus cached reduced multiples” is therefore not a new F6 idea.
- [GBLA](https://arxiv.org/abs/1602.06097) exploits the block structure of
  Gröbner matrices. It is a reference for separating sparse pivot blocks from
  dense trailing updates instead of full-matrix scalar elimination.
- [Groebner.jl learn/apply](https://sumiya11.github.io/Groebner.jl/interface/)
  exposes trace reuse across specializations. Reusing symbolic traces is an
  established technique; a useful contribution would be reliable application
  to our GF(2) parameter families, with explicit failure/fallback handling.
- [Magma's handbook](https://docs.magma-maths.org/CommutativeAlgebra/GrobnerBases/groebner.html)
  documents a dense F4 variant and NVIDIA GPU support in a special executable.
  GPU F4 is technically feasible and already has serious competition.
- [msolve](https://msolve.lip6.fr/) supplies a modern F4-based, vectorized,
  multithreaded solver. Its [published examples](https://msolve.lip6.fr/examples/index.html)
  provide useful prime-field comparison families.
- Two recent papers deserve full-method review before making a novelty claim:
  [GPU symbolic-preprocessing architecture](https://arxiv.org/abs/2601.06765)
  and [Proper-Cover](https://arxiv.org/abs/2607.09163). Their abstracts describe
  architectures/algorithms relevant to this direction; their claimed speedups
  have not been independently reproduced here and are not used as evidence.

## Proposed research program

### 1. Family-level reuse with checked specialization

Many point-decomposition queries share a curve, descent map and factor base,
while the target changes. Measure how much of the polynomial support, reducer
schedule and pivot structure is shared across those queries.

Learn a symbolic schedule on one target. For each new target, reconstruct the
actual coefficients, validate every required nonzero pivot, and fall back to
symbolic preprocessing when the schedule is no longer valid. Never reuse a
numeric basis or a signature criterion merely because supports look similar.
Small characteristic can make specializations fail frequently; measure the
failure rate and charge failed attempts to total runtime.

If a genuinely target-independent matrix block A exists, factor it once and
reduce target-dependent blocks using that factorization. A block decomposition
such as [[A,B],[C,D]] suggests a Schur-complement route after selecting an
invertible pivot block inside A. An arbitrary singular A cannot be inverted.
Use exact row operations, and account for fill-in and cached-factor memory.

**Experiment:** 64 unseen targets from one fixed family, baseline vs trace-only
vs trace plus shared-block reuse. Report total preparation + solve time, peak
memory, invalidated traces, completed targets and exact verification. The
primary metric is verified targets per second after charging amortization.

### 2. A sparse, signature-aware persistent reduction engine

Replace full `2^n` allocations with interned active monomials, indexed leading
terms, and on-demand reduced multiples. Track the basis version and reduction
dependencies of each cached multiple so new reducers invalidate or lazily
refresh affected tails. Add one optimization at a time, using M4GB/M5GB as
comparison points rather than reinventing them under a different name.

For a genuine F5 path, retain signatures in an ordinary polynomial ring with
explicit field equations, or prove an appropriate quotient-ring adaptation.
The current squarefree signatures, learned syzygies and unrestricted ordinary
normal forms are insufficient to claim classical F5 invariants. The repaired
completion makes the output correct, but does not turn the prepass into pure F5.

**Experiment:** compare the retained hybrid, a no-signature ablation, indexed
active monomials, and a signature-safe reference. Record pairs rejected, zero
rows, matrix dimensions, actual maximum processed degree and memory. Keep
field equations in the proof/certification path.

### 3. Adaptive degree growth versus partial assignment

Before creating the next large Macaulay matrix, estimate its shape from a
bounded symbolic pass. Compare continuing with splitting k variables and
solving the resulting smaller systems. Tune for the user's actual objective:
one verified relation, all roots, or a complete Gröbner basis. These objectives
must have distinct benchmarks.

Charge approximately 2^k subproblems when measuring exhaustive completion;
do not report the easiest branch as if it solved the whole problem. A pilot
sample estimates branch difficulty and whether regularity actually drops.
Overlapping subproblems can share reduced tails and traces where justified.

**Experiment:** fixed total wall/memory budgets, k=0..4, multiple unseen seeds,
explicit completed/inconclusive outcomes. A degree cap, first-fall degree and
degree of regularity are different measurements and must not be conflated.

### 4. CPU/GPU co-design

Keep pair selection, signature legality, sparse reducer lookup and pivot
discovery on CPU initially. Send dense trailing blocks or many independent
matrices to the GPU. Keep data resident and amortize command submission across
several panels; the retained small-panel results show why this is necessary.

For F5, group rows into batches whose allowed reducers respect signature
order. Arbitrary GPU RREF across labeled rows can invalidate signatures even
when it preserves the matrix row space. Preserve or reconstruct the required
provenance before using results in signature criteria.

The current Metal uint4 panel is a tested primitive. The next step is a full
CPU-pivot/GPU-update elimination path with exact CPU RREF comparison, followed
by integration behind a measured crossover threshold. For CUDA, use the same
packed GF(2) contract and test on actual NVIDIA hardware; this machine has no
CUDA compiler/device. No NVIDIA hardware was provisioned or paid for here.
For odd prime fields, use bounded exact integer modular arithmetic; floating
tensor operations cannot be assumed exact without an accumulation proof.

**Experiment:** compare CPU-only, resident GPU, and batched resident GPU on
captured real matrices. Include packing, transfer, pivot selection, dispatch,
table construction and extraction in the end-to-end result. Record rank and
canonical RREF, not only a checksum of a kernel output. The current panel
benchmark verifies every word but does not perform this complete solve.

## A credible global benchmark target

Maintain separate Boolean and prime-field leaderboards. Use descended Semaev
families, dense/sparse planted MQ, inconsistent and underdetermined controls,
cyclic/Katsura systems, MinRank/bilinear systems and real captured research
matrices. Include sizes that force degree growth and report censored timeouts.
Our present six-, nine- and twelve-variable fixtures are a correctness and
iteration corpus, not a high-regularity world-championship corpus.

Compare pinned versions of PolyBoRi, Singular, msolve, Groebner.jl and available
Magma/FGb implementations on the same machine where licensing permits. Pin
field, monomial order, input ordering, thread count, memory cap and output
contract. Hosted Magma timings versus local native timings cannot establish a
global ranking. Distinguish pure signatures, bounded prepasses, full bases,
root finding and matrix-only kernels. Publish the input corpus and correctness
certificates with the timings.

Success for the next campaign is an independently verified throughput win on
unseen targets with larger active monomial sets, followed by a reproducible
same-machine win against a strong external solver. A new “F6” designation
would require a distinct algorithmic contribution, its invariants and proof,
and broad ablations demonstrating where it wins.
