# Balanced exact pair descriptors preserve an N41 public relation

**The balanced six-pair direct-target XCNF contains the saved ordinary
N41 public relation, and a pinned control solved in 0.223 seconds.** The
complete control assignment satisfies every clause and native XOR row of
the separate unpinned public formula. The unpinned one-worker query reached
its frozen 120-second cap after active solver search, with no model or
terminal solver status line. An independent checked-Sage audit replayed
the six pair states and public-point group equation and verified both
terminal receipts.

## Exact method and frozen point

The supplied target is `Q=(1458168294740,1672312028033)` on
`EC1N41Ckb1h7d5e80d3c4d0` over `GF(2)[t]/(t^41+t^3+1)`, with subgroup
order `549756390943`. Six W8 fixed-sum pair blocks at Frobenius rotations
`[0,6,12,18,24,30]` use **B=960** actual subgroup-usable factor-base
points and **K=77** folded columns, as recounted from the frozen
six-rotation source rows in the [base-count audit](base_count_audit.json).
Each block has 160 signed states but
only 80 exact `(seed code, pair-output phi)` descriptors; each descriptor
has two group signs with the same columns. The [circuit](circuit.py)
chooses one descriptor per block, excludes repeated columns across blocks,
and links their three pair-pair sums to the raw public target through a
balanced five-link S3 tree. Four one-hot flags represent the raw points
whose cofactor-four projection equals `Q`.

The [preflight](preflight.json) checked the saved public relation against
all six descriptor domains, its 12 distinct folded columns, four exact
internal group sums, and its raw target branch. The
[protocol](protocol.json) bound 21 source and input hashes, a checked
[Sage runtime](sage_runtime_info.json), one solver worker, a 30-second
control cap, a 120-second public cap, and 4 GiB combined RSS before either
solver run. This stage is proposal `Q20261009183100`, with `candidate_id`
and `run_id` null until a complete IC pipeline is specified.

| Frozen XCNF quantity | Unpinned public formula |
| --- | ---: |
| Variables | 16,915 |
| CNF clauses | 31,308 |
| Native XOR rows | 6,822 |
| AND gates | 8,968 |
| Formula bytes | 705,163 |

## One-point query and independent checks

| Run | Terminal status | Charged target-dependent wall | Peak parent-plus-solver RSS |
| --- | --- | ---: | ---: |
| [Pinned known public relation](control/result.json) | `FOUND_VERIFIED_RELATION` | 0.222904375 s | 33,685,504 B |
| [Unpinned public query](public/result.json) | `ONLINE_TIME_CAP` | 120.137505750 s | 119,029,760 B |

| Exclusive phase, nanoseconds | Pinned control | Unpinned public |
| --- | ---: | ---: |
| Target preimages and formula construction | 74,345,750 | 57,923,125 |
| Solver execution, including failed search | 104,776,458 | 120,062,932,125 |
| Model and relation checking | 43,739,583 | 16,490,584 |
| Interval overhead | 42,584 | 159,916 |
| **Charged total** | **222,904,375** | **120,137,505,750** |

The target-preimage subphase is already included in formula construction;
its exact counter remains in each run receipt. Formula construction and
the clocked target query begin after target-independent geometry loading.
The public solver log reached approximately 863,000 conflicts and 1,428
restarts before the parent cap; its stderr is empty. The raw stdout,
stderr, formula hashes, process exit, guard, and phase counters remain in
the [run receipts](public/result.json).

The [full-XCNF audit](formula_audit.json) checks the control model against
all **31,308** clauses and **6,822** native XOR rows of the unpinned public
formula. The [checked-Sage audit](audit.json) independently reconstructs
24 sampled pair states, the six witness pair sums, the cofactor-four
public-point equation, and both terminal receipts. The public result is a
censored search observation with an explicit admissible assignment in its
exact formula. These local wall times have no host-isolation receipt and
are algorithmic diagnostics.

## Next solver gate

The balanced exact-descriptor tree removes the 640-entry target-derived
one-pair residual selector used by the earlier
[backward formula](../n41_w8_fixed_sum_backward_20261009/RESULT.md), but
its unpinned search also reached the 120-second cap. Together with the
[full cubic residual rank](../n41_two_pair_residual_degree3_20261009/RESULT.md),
this directs the next method toward an implicit constraint that uses pair
labels or seed sums and the public target to reject several still-free
pair families before their outputs are enumerated. The existing exact
rank-12 pair inverse supplies a check for proposed outputs; the missing
algorithmic step is to **generate or exclude** compatible outputs cheaply.
The first acceptance test remains an unpinned N41 relation with complete
attempt accounting, followed by a source-bound N131 600-second/4-GiB
whole-search estimate and independently replayed ordinary relation.
