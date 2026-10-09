# Full affine x-rank in every N41 two-pair seed-sum bin

**All 3,969 exact seed-sum bins have full affine rank 41 in the 40 free
bits of the completion x coordinate.** For each fixed pair of six-bit
nonzero seed sums, 41 valid, four-column-distinct two-pair completions
give linearly independent rows `(1,x_1,…,x_40)` over `GF(2)`. The
[independent checked-Sage audit](audit.json) replayed all 162,729 rank
witnesses using its own elliptic-curve arithmetic and obtained rank 41
in every bin. Thus no nonzero affine equality in the completion x bits
can exclude a residual while both seed sums are fixed on this frozen N41
policy. The known subgroup trace equation fixes x bit zero and is omitted
from the 40 free-bit feature vector. Here `x(2P)=λ²+λ` on the declared
curve, every odd-order subgroup point is a double, and the field basis
has `Tr(t^i)=0` for `1≤i≤40` and `Tr(1)=1`; hence the polynomial-basis
bit zero of every subgroup x is zero.

## Exact method and certificate

The [frozen protocol](protocol.json) binds the same
`EC1N41Ckb1h7d5e80d3c4d0` W6 pair domains at rotations 20 and 30,
the [full independent occupancy census](../n41_two_free_pair_occupancy_20261009/README.md),
and the [sign-orbit certificate](../n41_two_pair_sign_orbit_x_support_20261009/RESULT.md).
Each pair state contains two factor-base leaves with different folded
columns. The pair-of-pairs condition requires all four folded columns to
be distinct. Simultaneously negating both pair states preserves their
seed sums and columns and preserves the x coordinate of their sum, so the
producer visits one representative of each of the 1,583,568 sign orbits.
The 3,969 nonzero seed-sum pairs each contain 128–832 such orbits.

For one bin `(s,t)`, let `M_{s,t}` have a row `(1,x_1,…,x_40)` for every
valid orbit with seed sums `(s,t)`. An affine necessary equation is a
vector in the right kernel of `M_{s,t}`. The [producer](run.py)
retains 41 independent valid point-index witnesses per bin and stops
evaluating group sums for that bin once rank 41 is reached. These
`41 × 3,969 = 162,729` saved rows are a finite rank certificate:
additional valid rows cannot reduce rank, and the matrix has only 41
columns. The Sage auditor independently rebuilt the source points,
all 3,912 states in the two pair domains, their sign maps, and the
1,583,568 valid assignment orbits by column masks. It then recomputed
every saved group sum and its binary rank. The saved count and rank cover
every bin, rather than a sample of bins.

The full-rank result also rules out a global affine map that recovers any
nonconstant seed-sum bit from the residual x: restricting such a map to
one bin would give a constant affine expression in x, which full rank
forces to be the same constant in every bin. The seed bits vary across
the 3,969 bins. Nonlinear equations, seed-conditioned inequalities,
and target-coupled elimination through additional pair blocks remain
available.

| Frozen diagnostic | Result |
| --- | ---: |
| Valid sign orbits partitioned | 1,583,568 |
| Seed-sum bins | 3,969 |
| Affine rank in every bin | 41 / 41 |
| Deficient bins | 0 |
| Independent Sage group-rank witnesses | 162,729 |
| Producer wall / peak RSS | 6.169 s / 62,013,440 B |
| Sage audit wall / peak RSS | 7.077 s / 310,919,168 B |

The source and protocol were committed before the producer ran. The
[checked-Sage runtime receipt](sage_runtime_info.json) was saved before
the auditor launched. Both stages stayed within their frozen 300-second,
4-GiB diagnostic caps. The host lacks an isolation receipt, so the times
are exploratory certificate costs, not a solver or IC speed comparison.
The [compressed run receipt](result.json.gz) preserves the exact bytes of
each witness and bin count; the [audit receipt](audit.json) binds the
uncompressed result and runtime hashes. Run [verify_archive.py](verify_archive.py)
to check the archived bytes without extracting into the worktree.

## Method decision

An affine x-bit prefilter conditioned on the two free pair seed sums
cannot supply the missing N41 early pruning. The next constructive
method should carry nonlinear pair-realizability constraints or eliminate
several pair blocks jointly against the public target. A valid successor
must still recover an unpinned ordinary row on the frozen N41 control
without a quadratic pair-sum index and then justify its exact N131 work
and memory under 600 seconds and 4 GiB. This rank certificate concerns
the N41 factor-base policy; it is not an N131 rank assertion. Complete
candidate and run IDs remain null.

The producer and audit are write-once. For a new execution, copy their
sources and protocol beside the same immutable input directories into a
fresh directory without the saved output receipts. Run
`PYTHONDONTWRITEBYTECODE=1 python3 run.py`, save the checked launcher's
`--runtime-info`, then run
`/Volumes/SSD990/cryptanalysis/sage -python audit.py`. To replay the
saved audit from the archive, decompress `result.json.gz` byte-for-byte
to `result.json` in a separate copy and omit the saved `audit.json`.
