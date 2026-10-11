# Next experiments: complete queries and the F6 hypothesis

The current two-block symmetry is a constant-factor reduction in representative
work. Full specialization and expanded verification remain. Choose the next
implementation from the measured exclusive phase costs; do not infer total
speedups from branch counts or multiply ratios across separate runs.

## First CPU experiment: defer full proof reconstruction

The affine stage updates the full equation/multiplier combination on every
pivot-row XOR. Test a producer that instead records which existing pivot rows
were used to reduce each newly inserted row. A dependency bit is toggled for
each row XOR; the full equation combination is reconstructed only when a row
reduces to the constant one.

With highest-column-first reduction, a stored pivot at column `p` depends only
on stored pivots at columns greater than `p`. Expanding dependencies in increasing
column order therefore terminates. XOR the original source-row IDs selected by
that expansion to recover the exact affine multipliers. Preserve every source
row's equation and multiplier slot. Ignore zero rows; they never become pivots.
This is a provenance representation experiment, not a new elimination algorithm.

The [generic GF(2) pilot](research/deferred_proof_pilot.py) compared the resulting combination bitsets with
full forward provenance on all 4,096 four-row, three-column matrices and 300
random matrices through 176 columns and 310 rows. Every bitset matched and every
returned identity was independently XOR-checked; tiny cases also used a complete
span oracle. This validates the prototype's reconstruction rule, not the native
implementation or any speedup. The native experiment must charge dependency
storage and reconstruction, enforce bounded memory/work, preserve CPU/UBSan and
unchanged-checker tests, and run the same paired complete-query measurements.

## GPU work within one query

First compare compact representative scheduling against the unchanged all-branch
Metal kernel. Map each compact index to one canonical fixed-block pair; cover
diagonal pairs once. Keep the fresh exact symmetry test and use the full grid
when it fails. Include packing, index calculation, launch, synchronization,
expansion, proof copying, and independent checking in complete-query timing.
This only addresses the current supported constant-linearization shapes.

For the 24/27-variable frontier, test a bounded GPU affine-certificate producer.
One query supplies many independent residual systems. Compare one lane versus
one cooperative subgroup per residual system, measuring register pressure and
spills as well as elapsed time. Preserve equation-combination provenance so
round34's checker can validate the resulting full identities. Cap proof output,
record exhausted work, and retain the CPU path. Extending constant elimination
to 36/45/55 features is a distinct intermediate experiment, not evidence that
affine elimination already runs on the GPU.

A GPU promotion requires repeated single-query wins against the best paired
CPU implementation. Throughput across different targets and requested backends
that fall back to CPU do not satisfy that gate. CUDA requires an actual rebuilt
and tested CUDA implementation on physical hardware before compatibility or
speedup claims; Metal measurements do not establish it.

## Reusable elimination with certificates

Prior work constrains novelty. [Furue and Kudo's Polynomial XL](https://arxiv.org/abs/2112.05023)
partially eliminates a Macaulay matrix over a polynomial coefficient ring
before specializing its fixed variables. Its complexity comparisons use
explicit assumptions and heuristics. [Joux and Vitse's Crossbred](https://eprint.iacr.org/2017/372.pdf)
also combines elimination and specialization. A [parallel GPU Crossbred implementation](https://research.tue.nl/en/publications/implementing-joux-vitses-crossbred-algorithm-for-solving-mq-syste/)
was published by Niederhagen, Ning, and Yang. These are research comparisons,
not measured baselines for our complete-basis certificate boundary.

A concrete F6 working hypothesis is to choose a separator, partially eliminate
an invariant symbolic block, then reuse its exact derivation identities across
specializations of that *same fresh target*. It must lower the surviving matrix
dimension or certified work sufficiently to repay construction, evaluation,
exception handling, and proof checking. Reusing target-independent support
layouts is already implemented; it does not justify reusing numerical pivots
or answers across targets.

The first pilot should record original and surviving row/column counts, rank,
coefficient sparsity, coefficient degree growth, proof size, setup per target,
and total verified query time. Compare against F4/signature methods and the
best evaluation/interpolation arm on frozen systems, with identical completeness
requirements. A solver returning one root must not be compared as though it
returned and certified a complete reduced basis.

Required counterexamples include dense systems without small separators,
rank-changing specializations, vanishing proposed pivots, false symmetry,
and the retained inconsistent system with no affine-multiplier refutation.
Polynomial coefficients in the Boolean quotient can be zero divisors. Do not
divide by an unevaluated coefficient or assume a field argument survives the
quotient: either use valid division-free identities or account for all exceptional
branches. Independent checking must cover those branches too.

For incremental updates, measure the rank and support of the difference between
neighboring specialized matrices before implementing a low-rank update scheme.
A one-bit input change need not induce a low-rank matrix change. Keep random
dense controls and charge every failed update plus rebuilding to the same query.

An asymptotic claim requires a named input family, proved hypotheses, a bound
on the reduced dimensions and proof costs, and comparison at the same output
boundary. A smaller measured constant or a heuristic regularity assumption is
not such a proof. The present implementation establishes neither a novel F6
algorithm nor a globally fastest F4/F5 implementation.

## Full pipeline gate

After component gains, freeze a complete candidate manifest and solve one
previously unseen public target, independently verifying recovered scalar
replay and charging all target-dependent attempts and fallbacks. Pair rho on
the same point and resource envelope; record reusable preparation separately.
PDP component controls retain null candidate/IC/rho fields until that complete
pipeline experiment exists. Planted controls do not estimate natural yield.
