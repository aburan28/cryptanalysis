# ECC2K-130 degree-263 polynomial-W base screen

The first verified descending codomain did **not** show a two-percentage-point
rationality gain at W24 or W28 on the frozen, paired 16,384-mask samples.
W35 remains **inconclusive** at that material-gain threshold: its observed
descendant advantage was 1.23 points, with an approximate paired 95% interval
of +0.14 to +2.32 points. These are factor-base geometry observations, not
point-decomposition yields or an ECDLP speedup. The route is the merged
`IW1E263d1hadee4e69fa3d` source-to-first-descendant map, whose manifest now
also pins the exceptional-input replay.

The [protocol](PROTOCOL.md) and [config](CONFIG.json) were committed before
new masks were generated, then the producer and [independent verifier](verify.py)
were committed and pushed. The first launch rejected a stale local copy of
the route-manifest hash **before sampling**; its raw failure and the
pre-outcome correction are preserved in [PRECHECK.md](PRECHECK.md). The one
completed run used the unchanged SHA-256 mask domain, sample sizes and gate.
It passed a separate replay of **all 49,152 predicate rows** and **192 full
point/projection controls**. The replay reconstructs the basis by integer
XOR, computes trace by explicit Frobenius summation, checks both rationality
bits per mask, and checks the curve law, 2-torsion translation, `[4]`
projection, subgroup order and signs for the controls. The [verification
receipt](evidence/run-r2/verification.json) has `verified: true` and binds
both raw files by SHA-256.
A copied first-row predicate flip was rejected at the independent predicate
check even after the copied raw-file hash was updated in the copied summary.

| W dimension | Source rational / 16,384 | Descendant rational / 16,384 | Descendant − source, pp (approx. 95% paired interval) | Frozen 2-pp gate | Smaller arity `m` | Hard uniform-target support upper bound at `m` |
| ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 24 | 8,305 | 8,145 | −0.977 [−2.058, +0.105] | no material gain | 5 | 0.0005208333 |
| 28 | 8,151 | 8,174 | +0.140 [−0.954, +1.234] | no material gain | 4 | 0.000005086263 |
| 35 | 8,135 | 8,336 | +1.227 [+0.137, +2.316] | inconclusive | 3 | 0.00000007947286 |

The counts are for **the same masks** on both models, with 4,166/4,006,
4,170/4,193 and 4,048/4,249 source-only/descendant-only masks, respectively.
The approximate intervals describe the declared uniform-mask sampling model;
the fixed SHA-256 cohort is not a census. W35's positive difference is too
small and uncertain to meet the preregistered material-gain rule. A second
cohort chosen after seeing it cannot replace this result.

The last column is an unconditional counting bound, not an observed hit
rate. For any of these polynomial-W bases, a nonzero `w` has at most two
distinct subgroup points after `[4]`: its two `u` roots differ by rational
order-two translation, which `[4]` kills, leaving only the two signs. Thus
`B <= 2(2^d-1)`, giving respective maxima **33,554,430**, **536,870,910**
and **68,719,476,734** actual nonidentity points. Even if every possible
point exists and every unordered `m`-sum is distinct, uniform nonidentity
target support is at most `binomial(B+m-1,m)/(r-1)` with
`r=680564733841876926932320129493409985129`. The bound rules out a 1%
one-shot hit rate at the listed smaller arities. It does not rule out an
economical higher-arity implicit PDP, a different codomain base, or a
nonuniform query distribution.

The completed producer spent 0.738 s wall and reached 266,125,312 bytes
peak RSS on this unisolated macOS host; these are reproducibility data, not
an IC/rho comparison. It did not materialize a full factor base, determine
effective matrix columns, run a natural-target PDP, collect relations,
recover a logarithm, or measure rho. Those costs and `candidate_id` remain
null in [the summary](evidence/run-r2/summary.json). The source/transported
and native/pullback equality checks remain represented by the verified N39
toy panel and the exact route, while an **equal-actual-B, four-policy N131
PDP comparison** is still an open goal.

The [follow-on exact capacity gate](../ecc2k130-263-capacity-gate-20261004/RESULT.md)
quantifies the minimum actual base sizes for m3–m8 and separates sign-only
from explicitly orbit-closed relation-column policies. It does not turn
this screen into an IC result or close the four-policy PDP gap.

This result deprioritizes W24 five-summand and W28 four-summand native-base
claims as routes to a high one-shot yield. The next informative degree-263
gate is a base whose exact useful size and folded columns can be charged,
followed by held-out **ordinary m≥3 PDP** results for source, transported,
descendant-native and pullback policies at equal `B`. A W35 rationality
confirmation is secondary until such a PDP/cost path makes a roughly
one-point density shift consequential. None of these stage observations
changes the canonical IC-versus-rho scoreboard.

The raw files, empty/failed first attempt, runtime receipt and source hashes
are covered by [SHA256SUMS](SHA256SUMS). From the repository root, use the
checked launcher and fresh output paths to reproduce the full run:

```sh
./sage --runtime-info > experiments/ecc2k130-263-w-screen-20261004/runtime-info.json
./sage -python experiments/ecc2k130-263-w-screen-20261004/run.py \
  --out-dir /tmp/ecc2k130-263-w-new-run
./sage -python experiments/ecc2k130-263-w-screen-20261004/verify.py \
  --run-dir /tmp/ecc2k130-263-w-new-run \
  --out /tmp/ecc2k130-263-w-new-verification.json
shasum -a 256 -c experiments/ecc2k130-263-w-screen-20261004/SHA256SUMS
```

Run these commands in a disposable clean checkout: `run.py` deliberately
binds the checked launcher's `runtime-info.json` hash to its receipt, and
the command above refreshes that tracked file for a new runtime. Keep this
startup check outside the stage timer and do not overwrite the archived
`evidence/run-r2` output path.
