# Exact-four counter removes 93,654 variables from the normal4 m6 formula

An exact four-state threshold counter reduces the frozen balanced ECC2K-130
normal4 four-lift formula from **536,683 to 443,029 variables** and from
**599,988 to 418,074 ordinary clauses**, with the same 300,963 native XORs.
This is a 17.451% variable and 30.320% clause reduction while preserving the
same `B=11,743,888` usable source points. A four-support-index encoding also
passes exact membership controls but produces a slightly larger full formula:
443,185 variables, 422,172 clauses, and 301,251 XORs. Both new ordinary
query-zero searches entered CryptoMiniSat's restart loop and reached the
frozen 150-second external wall cap with `BOUNDED_UNKNOWN`. Their raw
transcripts and independent audits are retained; neither bounded attempt
contributed a verified relation or a rank-increasing row.

## Exact selector and point controls

The [frozen protocol](PROTOCOL.md) compares only the normal4 leaf selector on
the source curve `EC1N131Ckb1h136f03e58c98`. It retains the parent's six
exact leaves, balanced five-S3 pair tree, ascending leaf-mask order, one
public query, and four certified raw target lifts. The legacy encoding uses
at-most-four on the 131 mask bits and at-most-127 on their complements. The
new counter instead uses at-most-four plus a four-threshold recurrence for
at-least-four. The support-index policy decodes four strictly increasing
**eight-bit** positions in `[0,130]`; seven bits would omit positions 128,
129, and 130. A sorted support tuple and a four-hot mask are inverse
representations of the same set. Neither policy changes the source point
equations or adds a post-solver membership filter.

Checked Sage [replayed 128 frozen normal4 source-point controls](runs/R1/sage_selector.json),
their `[4]` subgroup projections, the planted balanced six-point group sum,
and a separate rational source leaf with support `(0,1,2,130)`. Exhaustive
small-width support-mask bijections and duplicate, reversed, and out-of-range
index checks passed. The pinned native-XOR [control receipt](runs/R1/cnf_controls/receipt.json)
records 11 SAT/UNSAT outcomes across both policies: valid leaves including
position 130 are SAT; changed x, three/five selected bits, duplicate/reversed
indices, and index 131 are UNSAT. The parent's checked four-lift and leaf
controls remain prerequisites.

| Formula | Variables | Ordinary clauses | Native XORs | Build wall s | Builder peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy one leaf | 53,973 | 63,385 | 26,905 | parent receipt | parent receipt |
| Counter one leaf | 38,364 | 33,066 | 26,905 | 1.712 | 47,513,600 B |
| Support-index one leaf | 38,390 | 33,749 | 26,953 | 2.137 | 48,529,408 B |
| Legacy balanced m6, four lifts | 536,683 | 599,988 | 300,963 | parent receipt | parent receipt |
| Counter balanced m6, four lifts | 443,029 | 418,074 | 300,963 | 14.736 | 338,690,048 B |
| Support-index balanced m6, four lifts | 443,185 | 422,172 | 301,251 | 8.514 | 338,984,960 B |

The counter saves 15,609 variables and 30,319 clauses per leaf relative to
the legacy leaf; over the six-leaf formula that is exactly 93,654 variables
and 181,914 clauses. The support-index full formula saves 93,498 variables
and 177,816 clauses relative to legacy, but adds 288 native XORs. Both new
policies exceeded the preregistered 10% full-formula size gate. The
[deterministic archives](runs/R1/archives.json) reproduce every raw XCNF
SHA-256, including the four built formulas and 11 pinned controls. The full
counter and support-index XCNF SHA-256 values are
`21b4c7c292fd1441f127428927fb6cf6c51849e279d97e72adbbd95343048d79`
and `13013b869bfa8a3a6ec9e8857425e8092c119ed17adf27ed1e8a8cd3963ba850`.

## Bounded ordinary search and accounting

Pinned CryptoMiniSat 5.14.7 SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`
ran one thread and native XORs with `--maxtime=120`, external 150-second wall
guard, and 4 GiB RSS guard. The host has no CPU-isolation receipt; build
and solver wall times are exploratory stage costs and are not comparable as
speed ratios. The four target lifts and source base were prepared before
these intervals. The attempts do not include relation checking, matrix
construction, descent, or scalar replay.

| Policy | Status | Solver wall s | Peak observed solver RSS | Live restart rows | Last displayed conflicts | Verified relations | Novel rank |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
| Counter | `BOUNDED_UNKNOWN` | 150.304 | 328,876,032 B | 481 | `166K` | 0 | unknown |
| Support index | `BOUNDED_UNKNOWN` | 150.074 | 322,879,488 B | 643 | `235K` | 0 | unknown |

The rounded conflict cells come from the last live `c rst` rows, not terminal
exact conflict totals. Both external guards killed the solver with exit `-9`
before a terminal solver status. The independent [counter](runs/R1/counter_audit.json)
and [support-index](runs/R1/support_index_audit.json) audits bind the formula,
receipt, runner, and raw stdout/stderr hashes and check live search. The
first counter attempt stopped during formula reading when the sandbox denied
the runner's `ps` RSS probe. It is retained as a separate
[`PRODUCER_FAILURE` receipt](runs/R1/counter_probe_attempt0.json) with raw
transcripts and `solver_search_started=false`; the runner was then fixed to
record such failures, committed, and rerun with process inspection available.

## Decision

Use the counter encoding as the normal4 circuit baseline: it is strictly
smaller than the support-index circuit in all three XCNF dimensions, passes
the same exact point and SAT controls, and leaves the native-XOR arithmetic
unchanged. Keep the support-index encoding as a distinct search representation
for later controlled study; its 643 versus 481 restart rows on this contended
host are not a performance ranking. Both ordinary outcomes are censored, so
the current data do not estimate natural relation yield or useful-row cost.
Do not expand the 16/256-query N131 prefixes from this gate. The next
algorithmic work should complete the degree-263 exceptional-input transport
proof and the charged n53 compact-orbit setup/recovery gate, then return to
N131 PDP search with a structurally different relation producer before
opening held-out four-policy queries. The 44,824 potential normal4 orbit
columns remain a geometry count, not final matrix rank. `candidate_id`
remains `null`; the [manifest](runs/R1/manifest.json) binds the evidence.
