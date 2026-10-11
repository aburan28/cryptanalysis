# Joint-linear inverse for exact N131 W18 pair outputs

**A supplied W18 pair-output coordinate now admits one 131-by-53 binary solve instead of a 262,143-seed scan whenever the joint map has full rank.** On the frozen N131 panel, the solve recovered both archived source pairs exactly, rejected a published-point coordinate by augmented rank, and matched the established all-seed oracle on every output. Independent checked Sage reconstructed all four matrix ranks, both seed/product solutions, and both raw group-sign witnesses. Two consistent lower-rank coordinates exercised the complete all-seed fallback and matched its exact witness sets.

The exact curve is `EC1N131Ckb1heb5f1998f20b` over `GF(2)[t]/(t^131+t^13+t²+t+1)`, with subgroup order `680564733841876926932320129493409985129`. The six-rotation W18 source has **1,575,684 usable base points** and **131,068 folded columns**; the audited unrotated support has 131,307 rational source masks. This is a supplied-coordinate decomposition component with `candidate_id: null`.

For W18 seed masks `a,b`, let `s=w_a+w_b` and `p=w_aw_b`, and unrotate the proposed reciprocal output coordinate to `c`. The exact pair equation is

`(1+p²)c²+pc+s²=0`.

Here `s` belongs to the 18-dimensional span of `t¹,…,t¹⁸`, while `p` belongs to the 35-dimensional span of `t²,…,t³⁶`. Both spans are exact in the degree-131 field. For fixed `c`, the map

`F_c(s,p)=s²+cp+c²p²`

is binary linear on 53 coefficient bits. The [native implementation](native.cpp) inserts 18 seed-square and 35 product columns into a 131-row pivot basis and tests whether `c²` is in the image. At rank 53, a consistent solve uniquely fixes `s,p`; the exact rank-17 fixed-sum inverse then recovers the unordered source masks and checks rational support, distinct folded columns, product equality, and the pair equation. An inconsistent augmented system has no W18 source pair. A consistent rank-deficient system enters a complete seed-and-branch fallback. Each returned pair still undergoes group-sign replay.

The [frozen four-case protocol](protocol.json) reused two true raw pair outputs, a published-point raw coordinate, and a trace-one field control from the prior [all-seed inverse](../n131_w18_allseed_linear_query_20261011/RESULT.md). The online component interval starts with the supplied coordinate, includes unrotation, the joint solve, witness checks, and any fallback, and stops before result serialization. Both arms exclude source loading; the prior arm also excludes its reusable all-seed map construction. One worker, a 120-second query cap, and a 4-GiB RSS cap were fixed before the runs.

| Frozen coordinate | Rank / augmented rank | Exact source pairs | Joint query | Prior all-seed query |
| --- | ---: | ---: | ---: | ---: |
| W18 seed 13,686, rotation 26 | 53 / 53 | 1 | 29.709 µs | 101.080 ms |
| W15-subspace seed 12,004 | 53 / 53 | 1 | 24.709 µs | 225.763 ms |
| Published-point raw lift 0 | 53 / 54 | 0 | 14.875 µs | 181.626 ms |
| Trace-one coordinate `c=1` | 44 / 45 | 0 | 14.042 µs | 3.167 µs |

The first three intervals show the effect of replacing up to 524,286 candidate-product/image checks with one joint solve and at most one fixed-sum inverse. The trace-one control takes longer than the prior direct trace exit; a constant-time trace precheck can recover that branch if this component enters a larger worker. Local CPU times are exploratory because the host has no isolation receipt. Peak measured RSS was **2.59–2.61 MB** on the four joint queries versus about **160 MB** for the prior map-based executable. The [case receipts](case_000.receipt.json) through case 003 preserve exact result hashes and parent intervals; [comparisons](case_000.comparison.json) through case 003 retain the prior query intervals.

The [independent checked-Sage audit](audit.json) formed a separate 131-by-53 `GF(2)` matrix, checked all ranks and augmented ranks, solved both positive systems, verified the seed masks and field products, and replayed two raw sign assignments for each pair. Its [runtime receipt](sage_runtime_info.json) was saved before the job. A consistent rank deficiency does occur for field monomials `c=t` and `c=t²`: both have rank 45. The [frozen fallback comparison](fallback_protocol.json) scanned all 262,143 seeds for each, matched the old oracle's zero-hit witness sets exactly, and finished in **2.458 s** and **4.135 s** with about **8.91 MB** peak RSS. These exceptional query intervals include fallback construction and remain under the frozen resource cap; they are slower than the older precomputed-map query on this host. The [terminal audit](terminal_audit.json) binds source and binary hashes, every comparison, Sage replay, and both fallback receipts.

This inverse makes proposed pair coordinates cheap to check on the full-rank branch. The next algorithm gate is to **derive those coordinates jointly from the public target while at least two pair domains remain free**. The frozen N41 eight-point public-target control requires an unpinned relation with measured early target-dependent pruning; a corresponding N131 worker then needs a source-bound 600-second/4-GiB whole-search projection before its ordinary query. Relation yield, useful rank, factor logs, and paired one-target online timing enter the candidate record after that construction succeeds.

To reproduce the completed panel, compile [native.cpp](native.cpp) with `clang++ -O3 -std=c++17 -Wall -Wextra -Werror`, then run `python3 run.py run`, `python3 fallback.py run`, and the checked `/Volumes/SSD990/cryptanalysis/sage -python` on `audit.py run` in a fresh copy of this write-once experiment directory. The saved files here are immutable receipts; the scripts refuse to overwrite them.
