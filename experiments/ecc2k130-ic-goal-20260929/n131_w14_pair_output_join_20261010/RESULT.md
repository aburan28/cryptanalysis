# Exact pair-output join cuts the four-atom proposal check

A reusable table of two-atom output coordinates replaces the degree-eight
resultant/GCD scan for a **proposed same-seed four-atom output**. On the
frozen N131 `W14`, `s=t` control, source filtering leaves **2,062 actual
rational, distinct-column source pairs** and **4,124 pair-output entries**.
The source-filtered join recovered the same two constructed product
witnesses as the archived exact resultant and rejected the same trace-zero
control. Its measured native query intervals were `0.216598` and
`0.212987` seconds, versus `2.398859` and `2.141697` seconds for the
matched resultant scan on this host. The ratios `11.075` and `10.056`
are exploratory stage diagnostics; CPU isolation and a complete
single-target IC pipeline remain separate gates.

## Method

For `y²+xy=x³+1` over `GF(2^n)`, write `w=1/x(P_w)` and fix a nonzero
source-pair sum `s`. Each source pair has product `p=w(w+s)` and its
reciprocal pair-output coordinate `C` satisfies

`g_p(C)=(1+p²)C²+pC+s²=0`.

The setup enumerates each product in the source image `V_s`, solves this
quadratic, and stores every root `C -> p`. Given a proposed four-atom
output `z`, the reciprocal S3 equation becomes a quadratic in the
complementary pair output `D`:

`(1+z²C²)D²+zCD+(z²+C²)=0`.

For each stored `C`, the query solves this equation and looks up each
root `D`. All algebraic product witnesses are emitted. Both native
variants use the frozen field implementation; the Artin-Schreier branch
replays one root in its defining equation and obtains the other by
adding the known root sum. In odd field
degrees 41 and 131, the root solver uses the half-trace for the
Artin-Schreier case, with explicit linear and square-root branches.
Actual source points, sign choices, folded columns, and group sums still
require replay before a relation enters the matrix.

The first [protocol](protocol.json) freezes the source, both binaries,
four N41/N131 inputs, resource cap, and eight-run order before the
matched unfiltered comparison. Its [result](result.json) shows the join
matched the archived exact algebraic hit sets on all four controls.
The [filtered protocol](protocol_filtered.json) additionally binds the
independently audited [W14 source support](../n131_w14_ten_source_gate_20261009/support_w14.tsv),
the filtered binary, and the six-run N131 order. Both use one worker,
120-second parent caps per run, and a 4-GiB RSS limit. Native setup and
query clocks are separate. The [audit](audit.json) compares every hit
with the earlier independent checked-Sage group replay, verifies the
source-mask products and support count, and checks raw result identities.
The [functional rebuild](rebuild.json) compiled both retained sources
again and reproduced all six positive/control output sets and table
sizes. A byte-for-byte comparison failed for the separately linked
macOS binary, as preserved in [the first rebuild attempt](rebuild_attempt_v1.json);
the rebuilt controls passed independently of that binary identity.

| N131 proposed output | Resultant query s | Unfiltered join query s | Source-filtered join query s | Filtered setup s | Filtered peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Constructed four-atom output | 2.398859 | 0.410840 | **0.216598** | 0.109228 | 3,162,112 B |
| Frozen trace-zero control | 2.141697 | 0.394687 | **0.212987** | 0.114551 | 3,112,960 B |

The unfiltered N131 table has 8,191 distinct pair outputs from 8,192
algebraic product states. Exact W14 rational-mask and distinct-column
screening gives 2,062 source pairs and 4,124 distinct outputs; the
constructed source masks `(18,19)` and `(24,25)` remain. The N41
unfiltered table has 33 outputs; its constructed case yields exactly
`(p,q)=(24,72),(72,24)` and its control yields none. At N131 the
constructed case yields `(1112,1376),(1376,1112)` in all three
variants, and the control yields none. The archived Sage audit checks
the positive source points and four-atom group sums independently.

The reported query intervals are monotonic-clock native intervals for
one proposed `z`; setup builds a reusable fixed-seed table outside that
interval. The parent receipts preserve launch, process, and archive
overhead separately. This is a proposed-output oracle, so the table's
diagnostic ratio is not the objective's one-target online IC/rho ratio.
The exact algorithmic change is 8,192 degree-eight GCD tests per
proposed `z` versus 4,124 quadratic solves and indexed lookups after
source filtering. `candidate_id` remains `null`.

## Target-conditioned next gate

The next experiment should generate `z` values jointly with the frozen
public point and the other free four-atom blocks. The 4,124-entry
fixed-seed table fits comfortably in the 4-GiB envelope and can be
reused across proposals; scanning uniformly chosen `z` values does not
address the public-target constraint. Start with the unpinned N41 public
point, record proposed `z` count, table queries, early rejection of
whole source families, full group replays, verified relations, novel
rank, wall and RSS. Promote a source-bound design to the N131 public
point only after that N41 relation gate passes.
