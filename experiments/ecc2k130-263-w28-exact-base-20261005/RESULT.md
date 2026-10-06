# ECC2K-130 W28 exact factor-base census

The verified first degree-263 descendant provides no material density gain
for this exact trace-zero W28 policy. Across all 268,435,455 nonzero masks,
the source has 268,436,324 usable subgroup points and the descendant has
268,465,880, a difference of 29,556 points or **+0.00550523402357561150
percentage points** in rational-mask density. This is far below the
predeclared two-percentage-point material-gain gate. Both bases pass the
60,591,280-point **necessary** W28/m5 size gate for a 1% one-shot uniform
target support count. Neither has a measured natural PDP hit rate, useful
relation rank, matrix solve, target logarithm, or IC/rho speedup.

The [protocol](PROTOCOL.md) and [configuration](CONFIG.json) were published
before the full enumeration. They fix the field, same paired W28 masks,
verified degree-263 route `IW1E263d1hadee4e69fa3d`, source curve
`EC1N131Ckb1h136f03e58c98`, first descendant
`EC1N131Cbinh833014327b07`, two batch sizes, limits, verification cohorts,
and decision thresholds. The W28 basis is
`span(t^j+Tr(t^j),1<=j<=28)` over `GF(2^131)` with modulus
`t^131+t^13+t^2+t+1`.

| Exact W28 quantity | Source | First descendant |
| --- | ---: | ---: |
| Rational nonzero masks `R` | 134,218,162 | 134,232,940 |
| Reciprocal pairs inside W28 | 0 | 0 |
| Sign-folded projected columns `C=R` | 134,218,162 | 134,232,940 |
| Distinct usable subgroup points before sign folding `B=2C` | 268,436,324 | 268,465,880 |
| Raw 17-byte-per-column log vector, excluding every other cost | 2,281,708,754 B | 2,281,959,980 B |
| W28/m4 one-shot uniform nonidentity-target support upper bound | 3.17895557601486942e-7 | 3.18035587427348179e-7 |
| W28/m5 formal mean unordered representations over all group targets | 17.0669432340111284 | 17.0763410244284630 |

The exact paired census is 67,121,094 masks rational on both curves,
67,097,068 only on the source, 67,111,846 only on the descendant, and
67,105,447 on neither. This replaces the earlier sampled W28 rationality
difference for this policy; that screen's confidence interval included the
exact result. Translation by the rational order-four point maps `w` to
`alpha/w`. The descendant `alpha` has polynomial degree 130, whereas the
product of two W28 values has degree at most 56; the source `alpha=1`
cannot be a product of nonzero trace-zero W28 polynomials. Thus no two
admissible masks collapse to the same signed `[4]`-projected point. The
native producer checked reciprocal membership on every rational mask,
and the independent point controls checked the rule on actual curves.

For subgroup order `r=680564733841876926932320129493409985129`, the
exact W28/m4 bounds use `binomial(B+3,4)/(r-1)` and remain well below
the 1% uniform-target objective, irrespective of F4, F5, SAT, FES, Gray
code, or crossbred implementation. The W28/m5 multiset count is large
enough to clear only a necessary size threshold. Its formal representation
mean is **not** an observed hit probability: duplicate sums, solving
failures, and dependent relations may sharply reduce useful yield. The
134-million-column sign-only ledger makes final matrix and log storage a
first-order part of any W28/m5 comparison. A raw log vector alone exceeds
2.28 GB; this excludes relation rows, basis construction, transport,
solver work, matrix overhead, and target descent. Frobenius-closed column
count remains unknown because this polynomial-W base has not been proved
closed under that action. These conditions explain why a full W28 base
cannot be promoted from a counting pass to an IC candidate.

## Evidence and replay

The [checked Sage runtime receipt](runtime-info.json) was saved before the
workloads. Native passes with inversion batches 2,048 and 8,192 each
enumerated every nonzero W28 mask and produced **byte-identical** 67,108,864-byte
two-bit membership streams. The [independent Sage verifier](verify_sage.py)
re-counted all four rationality cells from each entire stream, recomputed
both rationality predicates on 4,096 frozen SHA-domain masks, and replayed
256 full-width point-law controls per run. The point checks include the
order-four translation, `[4]` projection, subgroup order, and signed-point
keys. The separate d10 control replayed all 1,023 nonzero masks and every
resulting projected signed class, matched the prior W24 d10 stream, and passed the
[portable C++ backend check](portable_verification.json).

Both full raw streams are preserved as deterministic compressed evidence
in [run 1](runs/w28-b2048-r1/archive.json) and
[run 2](runs/w28-b8192-r2/archive.json). Each archive was unpacked into a
fresh directory: the decompressed hash matched the original, the checked
Sage replay produced the identical verifier receipt, and
[analysis.py](analyze.py) reproduced [analysis.json](analysis.json) using
only the compressed streams. The bit stream is a lossless encoding of both
ordered mask sets; the frozen field, half-trace, and `[4]` formulas recover
each signed subgroup pair. A formal `fb-archive` candidate manifest remains
separate work. The native census took 14.31 and 13.60 seconds with low
memory use on an unisolated Apple ARM PMULL host. Those times are
diagnostic, not CPU speedup claims.

From a checkout of this branch, replay either archive with fresh output
paths and the checked repository Sage launcher:

```sh
./sage --runtime-info > /tmp/ecc2k130-w28-runtime-replay.json
python3 experiments/ecc2k130-263-w28-exact-base-20261005/archive.py unpack \
  --run-dir experiments/ecc2k130-263-w28-exact-base-20261005/runs/w28-b2048-r1 \
  --out-dir /tmp/ecc2k130-w28-restored-r1
./sage -python experiments/ecc2k130-263-w28-exact-base-20261005/verify_sage.py \
  --run-dir /tmp/ecc2k130-w28-restored-r1 \
  --out /tmp/ecc2k130-w28-restored-r1/verification-replay.json
cmp /tmp/ecc2k130-w28-restored-r1/verification-replay.json \
  experiments/ecc2k130-263-w28-exact-base-20261005/runs/w28-b2048-r1/verification.json
```

Repeat with `w28-b8192-r2`. The producer accepts a fresh `--out-dir`,
`--dimension 28`, and either frozen `--batch-size 2048` or `8192`.
Save a new `./sage --runtime-info` receipt alongside any new workload
before launching it. Use [analyze.py](analyze.py) with both run directories
and a fresh `--out` to regenerate the machine-readable result.

The next stage is a frozen held-out ordinary-query comparison of W24/m6
and W28/m5, recording every solved, failed, timed-out, duplicate, and
rank-advancing query and charging matrix and target costs separately. Their
base sizes deliberately differ; that is a **policy** comparison, not an
equal-base-size solver comparison. For a four-policy source/native/isogeny
test, hold actual `B` and the query law fixed, and separately charge map
construction, transport, and any descended orbit handling. The conductor
change from 1 to 263 remains a structural fact, not evidence that native
descendant W28 improves useful IC yield. `candidate_id`, natural PDP yield,
rank, online time, verified logarithm, and rho ratio remain `null`.
