# Q1461: invert a fixed-midpoint sparse pair through its XOR sum

This proposal supplies an exact native kernel for a **fixed nonzero** `S3`
midpoint and two partially assigned normal-basis weight-bounded leaf x values.
It checks more partial pair completions without multiplying the two leaf
option counts. It is a point-decomposition stage component, not an ordinary
four-point solve or a complete index-calculus candidate.

The [frozen protocol](protocol.json) uses `Q1461`, `PDP4hybrid`,
`candidate_id: null`, `run_id: null`, and `isogeny: "none"`. N53 uses
`EC1N53Ckb1hf77aab617904`, the exact W≤4 factor base with `B=324,042`
actual usable points and `K=3,057` folded columns. N83 uses
`EC1N83Ckb1h876c2921cb64`, W≤6, `B=408,131,750`, and `K=2,458,625`.
The base digests and ordinary workload IDs are frozen in the protocol.
The two planted controls come from Q1448's independently checked four-leaf
witnesses; the 16 ordinary partial states per degree come from Q1446's
ordinary solver receipts. The protocol and implementation were committed
before the [result](result.json) was produced.

## Exact inversion

Write `s=a+b` and `p=ab` for two leaf x coordinates and fix midpoint `m≠0`.
The binary-curve summation equation is

`S3(a,b,m) = p² + m p + m² s² + 1 = 0`.

With `q=p/m`, solve `q²+q=s²+m⁻²`. In odd field degree, half-trace gives
one `q` exactly when the right side has trace zero; the other is `q+1`.
For each possible sparse XOR sum `s`, both resulting products `p` are
affine-linear functions of the normal-basis bits of `s`. Recover `a` from
`a²+s a=p` by binary elimination under its fixed-bit mask, then set `b=a+s`.
The linear map has a kernel of dimension at most one, so each branch has
at most two assignments. The kernel verifies weight, fixed bits, curve lift,
and direct substitution into `S3` before returning an ordered x pair.
For `m=0` it returns `skipped`; a caller must use a separate exact fallback.

The candidate sum bound is `Σ_{j=0}^{slack_a+slack_b} C(free_union,j)`.
It can be much smaller than the Cartesian product of the two leaf option
counts. The frozen probe separately enumerates every admissible ordered pair
and requires exact equality of the two pair sets. Its direct reference caches
leaf-lift results, but is not the optimized Q1458 batched-root solver.

## Frozen result and limit

Both positive controls recover the archived witness. All 32 ordinary
archived states agree exactly with direct enumeration and return zero pairs.
The counts below are sums over the stated rows; preprocessing of the
normal-basis product table is shown separately. They are exact operation
counts, not measured complete PDP costs.

| Degree and input | States | Sum candidates / direct pair candidates | Kernel mul / sqr / inv | Direct reference mul / sqr / inv | Verified pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 planted | 1 | 6,196 / 44,521 | 82 / 212 / 3 | 50,884 / 33,821 / 422 | 1 |
| N53 ordinary snapshots | 16 | 1,626 / 3,307 | 992 / 1,712 / 16 | 7,820 / 24,955 / 460 | 0 |
| N83 planted | 1 | 6,196 / 44,521 | 115 / 332 / 3 | 47,834 / 45,613 / 422 | 1 |
| N83 ordinary snapshots | 16 | 3,376 / 7,056 | 1,488 / 2,672 / 16 | 11,736 / 56,526 / 672 | 0 |

N53 preprocessing costs 2,809 field multiplications and 2,915 squares;
N83 costs 6,889 and 7,055. The [result](result.json) retains per-state
binary XOR counts and exploratory wall times. No host isolation receipt
exists, so these timings do not establish a controlled CPU speedup.
The native field counts do not include all SAT work, relation checks,
rank growth, matrix work, or target descent. A positive planted control
establishes correctness, not natural relation yield. The complete N131
`2^x` and successful ordinary-decomposition cost remain unknown.

## Next solver goal

Use this kernel as an exact fallback where the **sum** bound is affordable
even when the pair-product bound exceeds Q1458's 4,096 cap. In a changed
target-linked solver, measure how many new ordinary states are admitted,
the exact no-pair pruning rate, complete solver attempts, verified relations,
and cost per novel rank row at both N53 and N83. The main gate is an
independently replayed ordinary four-point relation. A faster check on the
same zero-yield fixed states is insufficient. If the admission and relation
gate fails, move to a rule that treats many intermediate x choices together
with the target rather than further tuning one fixed midpoint.

Reproduce with the checked Sage runtime receipt created before the run:

```sh
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/build.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/prepare_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/q1461_sparse_sum_inverse/run.py --check
```
