# Exact adjacent-window six-pair support favors same-rotation W15

The adjacent Frobenius-window pair inverse is an exact output checker, but
its enlarged seed space sharply reduces the support of the **two-shared-seed
six-pair IC policy**. On the degree-131 challenge curve, adjacent W14 has
at most **0.136449** signed twelve-point tuples per uniform subgroup
target before cross-pair folded-column exclusions. Adjacent W15 has
**34.933497**, versus **34,156.259** for the archived same-rotation W15
policy. Two complete exact counting algorithms agreed on every seed
bucket. These counts select same-rotation W15 for the next
target-coupled five-pair method gate.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, with
prime subgroup order `r=680564733841876926932320129493409985129`.
The W14 and W15 source files contain 8,220 and 16,441 audited rational
masks, respectively, with 8,160 and 16,381 signed-Frobenius folded
labels. A pair takes one source mask at rotation `r_i` and one at
`r_i+1`, for starting rotations `0,13,26,39,52,65`. Its two raw curve
signs per leaf give four signed states per accepted ordered mask pair.
The accepted pair has distinct folded columns. The normalized seed sums
of pairs 2 and 3 agree, as do those of pairs 4 and 5. Cross-pair column
exclusions and exceptional group outputs are omitted, making the counts
upper bounds for usable relations. The full twelve-window projected
factor-base count is not fixed here, so `candidate_id` and measured
target costs remain `null`.

## Exact count and one-prefix bound

For `W_d=span(t,…,t^d)`, the adjacent seed is
`s=w_a+w_b² ∈ W_d+W_d²`. That space has rank **21** at W14 and **23**
at W15. Let `c_s` be the number of signed, distinct-column ordered
pair states with seed `s`. The two free pairs contribute
`N=Σ_s c_s` states each; a constrained two-pair block contributes
`M=Σ_s c_s²`. The declared six-pair tuple ceiling is exactly
`T=N²M²`. Averaged over the order-`r` subgroup, `T/r` bounds the
fraction of uniform targets with at least one tuple when it is below
one. This is a group-wide bound; it does not decide the fixed published
point.

| Exact adjacent policy | W14 | W15 |
| --- | ---: | ---: |
| Accepted ordered mask pairs per rotation | 67,560,056 | 270,289,916 |
| Signed pair states `N` | 270,240,224 | 1,081,159,664 |
| Same-seed two-pair states `M` | 35,659,092,512 | 142,615,234,208 |
| Mean tuple ceiling `T/r` | **0.136449** | **34.933497** |
| Archived same-rotation mean | 33.324886 | 34,156.259 |
| Adjacent / same-rotation tuple count | 0.004095 | 0.001023 |
| One-free-pair prefixes required for 50% union-bound ceiling | **990,259,186** | **15,474,541** |
| Maximum all-stage time per such prefix in 600 s | 0.606 µs | 38.773 µs |

For a target-independent first-pair prefix, the remaining tuple count is
`C=N M²`, so the union-bound success ceiling reaches one half only after
at least `ceil(r/(2C))` distinct prefixes. The adjacent W14 threshold
exceeds **all 270,240,224 signed first-pair states**; its uniform-target
success ceiling is at most 13.645% even if every signed state is tried.
For W15, the archived same-rotation threshold is 7,914 prefixes under
the same input law. An adaptive method that selects prefixes using the
target has a different bound and must be measured directly.

## Frozen sources and verification

The [protocol](protocol.json) fixed source and baseline hashes, the pair
policy, one worker, 120-second count cap, and 4-GiB RSS cap before the
[count](result.json). For each width, the [producer](count.py) obtained
every one of the `2^21` or `2^23` seed-bucket counts in two ways:
direct NumPy enumeration of all accepted ordered mask pairs, and an
independent XOR Walsh convolution of the two source indicators followed
by exact same-column subtraction. The complete count arrays agreed
entry by entry. The retained histograms, count-array digests, exact
tuple integers, and source hashes permit replay without treating a
rounded mean as source data. The [independent integer audit](audit_result.json)
rechecked source cardinalities, same-column exclusions, histogram first
and second moments, subgroup means, baseline ratios, and minimality of
both prefix thresholds.

The W14 count took 6.981 seconds, W15 28.226 seconds, and the whole
producer 35.209 seconds, with 492,486,656-byte peak process RSS. These
are source-census stage observations on an unisolated host, not an IC
online interval or a controlled CPU speedup. The previous in-memory
direct and Walsh calculations yielded the same exact integers before
this source-frozen run.

## Next method gate

Keep the same-rotation W15 source and its stronger six-pair relation
support while developing a **public-target five-pair oracle**. The
existing signed-prefix Boolean kernel reached its 115-second bounded
search on one constructed residual, whereas 7,914 target-independent
prefixes within 600 seconds would permit at most 75.815 ms of complete
target work per prefix. A useful replacement must eliminate seed and
partial-output families jointly before that per-prefix search or select
prefixes from the public target. Its first executable gate is an
unpinned N41 public relation without a materialized four-point index,
with all failed proposals, independent group replay, and source-bound
N131 work and memory accounting. The complete goal continues through
ordinary N131 relation yield and rank, factor logs, fresh target
recovery, and same-point rho timing.
