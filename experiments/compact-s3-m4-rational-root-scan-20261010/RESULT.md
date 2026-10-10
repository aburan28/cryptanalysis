# Rational-orbit prefilter reduces N53/N83 fixed-output S3 work

The exact curve-lift test removes about half the sparse `x` masks before the
fixed-output S3 root kernel. On matched complete scans, it reduced charged
field multiplications by **38.87% at N53** and **39.98% at N83** with the
4,096-mask inversion window. All eight cells retained the predecessor's
complete pair decisions and exact pair witnesses. Checked Sage replay
independently verified each of the two distinct four-point control relations
on the named curves and bases. The reusable N83 rational-orbit census took
95.93 s, used 373,101 field inversions, and produced a 2,052,732-byte
representative file that all N83 scans shared.

This is proposal `Q20261010120000`, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`. The N53 curve is
`EC1N53Ckb1hf77aab617904`, with exact Q1301 W≤3 base `B=24,062` and
`K=227`. The N83 curve is `EC1N83Ckb1h876c2921cb64`, with exact Q1325
W≤5 base `B=30,977,592` and `K=186,612`. Each control or ordinary cell
uses the same frozen public point, fixed outer output, field representation,
and complete raw mask domain as the [matched predecessor](../compact-s3-m4-quadratic-root-scan-20261010/RESULT.md).

## Exact filter and charged stages

For nonzero `x` on `y²+xy=x³+1`, write `z=y/x`. Then

```text
z²+z = x+x⁻²,
```

so a `GF(2^n)`-rational point exists exactly when
`Tr(x+x⁻¹)=0`. Frobenius preserves this condition. Degrees 53 and 83 are
prime, and every nonzero sparse mask in these weight ranges has a full-length
Frobenius orbit. The [native producer](scan.rs) tests one representative per
orbit, saves only rational representatives, and expands those masks before a
target scan. An exact census assertion matches the rational raw-`x` count to
`B/2` for each established base. The cached representative files are
[N53](census/n53_representatives.bin) and
[N83](census/n83_representatives.bin); their hashes and one-time costs are in
the [census receipts](census).

| Complete scan, 4,096 window | N53 | N83 |
| --- | ---: | ---: |
| All nonzero weight-bounded masks | 24,857 | 30,967,383 |
| Rational masks / S3 root calls | **12,031** | **15,488,796** |
| Rational Frobenius orbits | 227 | 186,612 |
| Baseline → filtered target-scan field multiplications | 131,946 → **80,657** | 154,845,185 → **92,942,180** |
| Exact multiplication reduction | **38.87%** | **39.98%** |
| One-time census field inversions | 469 | 373,101 |
| One-time census wall, exploratory | 0.003 s | 95.93 s |
| Control / selected ordinary right pairs | 1 / 0 | 1 / 0 |
| Scan peak process RSS, maximum across two inputs | 7.4 MB | 258.4 MB |

The [frozen protocol](PROTOCOL.md), [freeze](freeze.json),
[build receipt](build_receipt.json), eight
[input manifests](inputs), [run receipts](runs), exact [pair-set audit](audit.json),
and [checked-Sage replay](sage_replay.json) bind the source, binary, inputs,
limits, statuses, and witness checks. Both 16,384-window cells per degree
also completed and agreed: N53 used 80,663 multiplications; N83 used
92,950,688. The 4,096 window used 6 and 8,508 fewer multiplications,
respectively, while the 16,384 window used fewer field inversions. This is a
two-value batch-window search on the same inputs. Each window's control hit
is a repetition of one relation per degree, not an additional relation.

All target-scan clocks start after the reusable orbit census and in-process
mask expansion. The [analysis](analysis.json) records those excluded intervals,
every scan interval, and peak RSS. N83 target scans ranged from 67.12 to
98.07 s on this unisolated, contended host; the predecessor's N83 intervals
were lower. The operation-count reduction is exact; these wall observations
are exploratory and do not establish a CPU speedup. The complete-process
receipts charge expansion and launch outside the target-dependent interval.

## N131 `2^x` work screen

The exact Q1413 W≤6 N131 base has `B=6,559,634,788`, `K=25,036,774`, and
`D=B/2=3,279,817,394` rational raw-`x` masks. Q1414's uniform
nonidentity subgroup-query bound requires at least **209,828,278** queries
for a 95% full-rank chance even if every returned representation supplies a
novel row. At one complete rational scan per query, that is at least
`2^59.26` S3 root calls. Transferring the measured N83 4,096-window rate of
`92,942,180 / 15,488,796` field multiplications per rational root gives
**`2^61.84` field multiplications**. This improves the predecessor's
conditional `2^62.58` by **0.74 bits** and remains **0.84 bits above
`2^61`** before query generation, base preparation, final matrix work, target
descent, or scalar replay. The measured N83 rate is an operation-ratio
extrapolation, not a challenge-width measurement.

The current source deliberately supports N53 and N83 only. Its full-mask
vector would use **52,477,078,304 bytes** at N131, above the stated 4-GiB
challenge gate. A streaming successor must keep only a bounded root window
in memory; its mask expansion and other target-dependent work must be
charged. The `2^61.84` screen assumes that successor preserves the measured
root-operation rate. The complete N131 cold and one-target online `2^x`
remain null because ordinary relation yield, novel rank, final linear
algebra, and target descent have not been measured for this pipeline.

Under the separate hypothesis that *each scanned fixed output* is uniform
over the entire `2^131`-element field, the rational-pair count gives an
even stronger necessary work screen: at least **`2^123.89` rational-root
calls** for 95% full-rank success. The proof counts at most `D(D+1)/2`
unordered rational-`x` pairs, each with at most two S3 outputs, then applies
linearity of expectation and Markov's inequality. The N53/N83 ordinary cells
fix one output each and do not establish this field-output law. For a
full-length Frobenius quotient, `D=nK`; consequently changing only the
weight cutoff does not remove this screen's approximate `0.95·2^n/n`
root-call boundary. The [analysis source](analysis.py) recomputes both
screens from exact receipts and records their distinct assumptions.

## Next experiment

Stream rational orbit representatives directly into bounded S3 root windows
on the same N53/N83 inputs, charging expansion inside each target scan and
checking exact pair-set equality. That removes the N131 mask-vector obstacle
without changing the mathematical source. The collector then needs a
target-conditioned output generator that avoids a complete scan per query;
measure its ordinary relation yield and novel rank on the exact N53 and N83
bases before assigning a complete challenge-size work exponent.
