# Q1505: deferred-y scan lowers the four-sign field-multiplication formula from 14B to 10B

The `PDP4hybrid` N83 second-pair scan needs only the output x coordinate
to query the exact factor-base key set. Q1505 computes the output y coordinate
only when that key hits, then checks the full group equation. Across eight
complete 512-pair-batch scans on the frozen selected and holdout ordinary
complements, the x-key checksums and hit counts exactly match Q1502. Four
additional complete scans screen 128- and 2048-pair batches. An independent
known-base control exercises and replays both signed branches.

For a scan with zero key hits and no equal-x exception, each positive base
representative uses five batch multiplication calls: one prefix product,
two inverse propagation products, and two slopes. Q1502 used seven, including
two unconditional y-coordinate products. All twelve ordinary N83 cells had
zero hits and zero exceptions. A complete four-sign scan thus changes from
`14B` to `10B` multiplication calls, a **28.57% or 0.485-bit reduction** in
this operation count. Batch inversion and squaring counts remain unchanged.
Inversion internals, key canonicalization, setup, and first-pair search are
separate work.

| N83 frozen base and scan | Q1502 | Q1505 |
| --- | ---: | ---: |
| Curve | `EC1N83Ckb1h876c2921cb64` | same |
| Actual usable points `B`; signed-Frobenius columns `K` | 30,977,592; 186,612 | same |
| Four-sign scan, batch multiplication calls | 433,686,288 | **309,775,920** |
| Ordinary 512-batch scans with identical key checksums | 8 | 8 |
| Additional 128/2048-batch scans | — | 2 / 2 |
| Exact-base hits in those 12 Q1505 cells | — | 0 |

The ordinary host lacked a CPU isolation receipt. Q1505 median scan seconds
were 23.65 over eight 512-batch cells, 23.36 over two 128-batch cells, and
14.03 over two 2048-batch cells. Run order and host load confound these
wall times; they do not establish a CPU speedup or a batch-size winner.
The 2,000,000-pair ABBA diagnostic in `paired_probe.json` preserves paired
exploratory times on one frozen complement.

On the exact N131 weight-at-most-six base, `B=6,559,634,788` and
`K=25,036,774` on `EC1N131Ckb1h6816f880945e`, the zero-hit formula gives
**65,596,347,880 = 2^35.933 multiplication calls** per complete four-sign
scan. It is an operation transfer from N83, not an N131 timing measurement.
Applying Q1414's necessary uniform-query counts to the explicit scenario of
one complete scan per query gives `2^62.652` calls at 50% rank success,
`2^63.578` at 95%, and `2^63.652` at expected rank `K`. These figures
exclude all other stages and assume a scan is performed on each query.

The independent uniform first-pair model prices relation supply more directly.
For each uniform nonidentity query, select a fixed first x-pair independently
of the target, and scan its four signed complements. Each complement can
match at most `B(B+1)/2` unordered signed-base second-pair sums. The union
bound makes the four-sign hit probability at most `2^-62.778` on the N131
subgroup. Under repeated independent queries, obtaining `K` hits requires
at least `2^87.356` expected complete scans, or **`2^123.289` batch
multiplication calls** with Q1505's formula. Q1502's formula prices the same
model at `2^123.774`; Q1505 improves it by 0.485 bits. Rank novelty,
first-pair selection, matrix work, target handling, inversion internals, and
replay are not charged. A target-guided first-pair method changes this input
law, so the figure is a model for the measured scan route, not a general
complexity bound on four-summand decomposition.

The fully charged N131 solve exponent remains unset. The next useful
experiment is a target-guided or indexed second-pair search that measures
ordinary exact-base relation yield, novel rank, and all failed attempts on
N53 and N83. The current scan formula gives a precise operation-count
baseline for that search.

The [protocol](protocol.json), [build receipt](build_receipt.json),
[ordinary result](result.json), [signed controls](control_result.json),
[analysis](analysis.json), and [read-only validator](validate.py) freeze
the source, inputs, outputs, and arithmetic. Recheck with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261012_n83_deferred_y_scan/validate.py
```
