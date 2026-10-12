# ECC2K-130 W24 exact factor-base census

The verified first degree-263 descendant does not increase the number of
usable points in this particular trace-zero W24 base. Exhausting all
16,777,215 nonzero W24 values gives 16,786,464 source points and 16,772,828
descendant points, a descendant deficit of 13,636. Both bases pass the
4,121,293-point **necessary** size gate for a one-shot six-summand policy,
but neither has a measured natural decomposition yield or relation rank.
These are factor-base geometry results, not complete index-calculus
candidates or speedup measurements; `candidate_id` remains `null`.

The [protocol](PROTOCOL.md) and [configuration](CONFIG.json) froze the field,
route, W basis, duplicate rule, limits, and verification before the census.
The source is `EC1N131Ckb1h136f03e58c98`; the first descendant is
`EC1N131Cbinh833014327b07` on the verified route
`IW1E263d1hadee4e69fa3d`. The paired comparison uses the same
`W24 = span(t^j + Tr(t^j), 1 <= j <= 24)` in
`GF(2^131)` with modulus `t^131+t^13+t^2+t+1`. The descendant's normalized
coefficient is derived from the route manifest, not selected from a
favorable screen.

| Exact W24 quantity | Source | First descendant |
| --- | ---: | ---: |
| Rational nonzero `w` values, `R` | 8,393,232 | 8,386,414 |
| Reciprocal pairs wholly inside W24 | 0 | 0 |
| Sign-folded projected columns, `C` | 8,393,232 | 8,386,414 |
| Distinct usable subgroup points before sign folding, `B=2C` | 16,786,464 | 16,772,828 |
| Raw 17-byte-per-column log vector, excluding all other costs | 142,684,944 B | 142,569,038 B |
| W24/m5 upper bound on one-shot uniform-nonidentity-target support | 0.0000163209595749986116 | 0.0000162547778873177378 |
| W24/m6 formal mean unordered representations over all group targets | 45.6618803259945615 | 45.4397791593455389 |

The exact paired mask table has 4,196,977 values rational on both curves,
4,196,255 only on the source, 4,189,437 only on the descendant, and
4,194,546 on neither. The descendant rationality difference is
-0.0406384492301016587 percentage points of the nonzero W24 population.
This supersedes an earlier 16,000-mask density screen for this exact policy;
that sample's uncertainty was broad enough to include the census result.

The order-four translation rule in the protocol maps `w` to `alpha/w`, where
`alpha^4=b` on the normalized curve. Since the descendant `alpha` has
polynomial degree 130 while the product of two W24 values has degree at most
48, a reciprocal partner cannot lie in the descendant W24. On the source,
the only possible partner product is 1, which cannot be made from nonzero
trace-zero polynomial W24 values. The native census checked every reciprocal
membership anyway. Thus these counts account for projection collisions:
`C=R` and `B=2R`. The independent small-dimension Sage control explicitly
reconstructs every projected signed point and confirms this counting rule.
Each canonical-mask stream is a lossless encoding of its two-point signed
subgroup classes under the field, curve, half-trace, and `[4]` formulas in
the frozen source and verifier. A formal `fb-archive` candidate record and a
complete IC manifest remain separate activation work; no `IC1` identity is
inferred from this count alone.

The W24/m5 upper bounds use the exact `B` values in
`min(binomial(B+4,5),r-1)/(r-1)` for subgroup order
`r=680564733841876926932320129493409985129`. They are about 32 times
tighter than the earlier geometric maximum bound, and reject a 1% one-shot
uniform-target coverage goal for this policy irrespective of whether PDP uses
F4, F5, SAT, FES, Gray code, or crossbred search. The m6 representation
means are **counting-only** quantities, not observed hit probabilities;
collisions, solver failures, and useful relation rank can only reduce the
real value. No matrix, target descent, logarithm, or paired rho interval was
measured. The [machine-readable analysis](analysis.json) leaves all such
fields `null`.

## Verification and evidence

The checked repository Sage launcher recorded [its runtime receipt](runtime-info.json)
before the workload. The native producer ran the complete census twice,
with inversion batch sizes 2,048 and 8,192. The canonical source masks,
descendant masks, and per-mask flags were byte-identical across runs. For
each run, the independent Sage verifier re-counted every flag, reconstructed
the complete canonical mask streams, and checked 184 seeded full-width point
controls, including the curve law, order-four translation, `[4]` projection,
and subgroup order. A separate [d10 control](controls/d10/verification.json)
reconstructed all 1,023 nonzero masks and all projected signed points; it
found 492 source columns and 495 descendant columns, exactly as enumerated.
The [portable-backend control](portable_verification.json) also recompiled
the same C++ source without ARM cryptographic instructions and reproduced
all d10 stream bytes; it checks the fallback code path, not full-width
performance.

The full-run raw streams are preserved as deterministic gzip archives in
[`runs/w24-b2048-r1`](runs/w24-b2048-r1/archive.json) and
[`runs/w24-b8192-r2`](runs/w24-b8192-r2/archive.json). Their manifests bind
the compressed and decompressed hashes, native binary, logs, summary, and
verification receipt. Both archives were unpacked into fresh directories;
each reconstructed stream matched its original hash, and the checked Sage
verifier produced a byte-identical receipt from each restored copy. The
[analysis script](analyze.py) also reproduced the committed analysis from
compressed streams alone. The observed 1.19–1.22 s native census timings
were taken on an unisolated host and are exploratory; no CPU speedup claim is
made from them.

From a checkout of this branch, use fresh output paths to replay either
archive. The checked launcher is required for every Sage job:

```sh
./sage --runtime-info > /tmp/ecc2k130-w24-runtime-replay.json
python3 experiments/ecc2k130-263-w24-exact-base-20261005/archive.py unpack \
  --run-dir experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1 \
  --out-dir /tmp/ecc2k130-w24-restored-r1
./sage -python experiments/ecc2k130-263-w24-exact-base-20261005/verify_sage.py \
  --run-dir /tmp/ecc2k130-w24-restored-r1 \
  --out /tmp/ecc2k130-w24-restored-r1/verification-replay.json
cmp /tmp/ecc2k130-w24-restored-r1/verification-replay.json \
  experiments/ecc2k130-263-w24-exact-base-20261005/runs/w24-b2048-r1/verification.json
```

Repeat with `w24-b8192-r2` to check the second run. To regenerate the
analysis from the compressed records, run `analyze.py` with `--run-one`,
`--run-two`, and a new `--out`, then compare it to [analysis.json](analysis.json).
The [producer](run.py) accepts `--dimension 24 --batch-size 2048` (or 8192)
and a fresh `--out-dir` for a new run. Run `./sage --runtime-info` and save
its output alongside that run before starting it.

The next decision is a held-out ordinary-query PDP and useful-rank panel
for the **actual** W24/m6 bases, with both curve policies paired on inputs
and with all failed and timed-out queries retained. In parallel, an exact
W28 base census would establish the actual `B` and columns for the competing
W28/m5 policy. The descendant isogeny remains a separate implementation
hypothesis: the ring conductor changes from 1 to 263, so any descended
Frobenius-orbit benefit must pay for map construction, recognition, and
transport. This census provides no evidence for choosing the descendant
solely to raise W24 base cardinality.
