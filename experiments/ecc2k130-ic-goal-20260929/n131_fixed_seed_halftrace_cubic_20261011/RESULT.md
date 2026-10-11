# Fixed-seed N131 pair circuit with halftrace-cubic group links

An exact change from the shifted reciprocal coordinate `z=1/(x+1)` to the
standard reciprocal coordinate `a=1/x` reduces the frozen N131 fixed-seed
ordinary public-point formula to **441,023 variables, 570,425 CNF clauses, and
249,569 native-XOR rows**. Relative to the prior formula on the same source and
public point, that is **50.408% fewer variables**, **41.300% fewer total
constraints**, and **36.192% fewer XCNF bytes**. The complete 16-point control
passes all **819,996** formula records and an independent signed curve-sum
replay. The ordinary one-worker query reached its 615-second parent cap with
status `BOUNDED_UNKNOWN`, 1,482 actual solver restart rows, and 729,366,528
bytes sampled combined peak RSS.

## Exact coordinate transform

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`, with prime subgroup order
`680564733841876926932320129493409985129`. The source is the audited W18
mask-to-column table, fixed XOR seed `212`, and eight Frobenius rotations
`0,16,32,48,64,80,96,112`. Its reduced BDD accepts exactly **33,191**
unordered rational, distinct-column source pairs per slot and has **13,093**
nodes. The selected source has **66,382 rational masks per rotation**,
**1,062,112 usable projected points** across eight rotations before orbit
folding, and **66,318 folded columns**. The complete pipeline remains a design
proposal with `candidate_id: null`.

For source coordinates `w_b=w_a+s`, let `h=H(s)` and `p=w_a w_b`. The previous
exact pair equation in `z=1/(x+1)` was

`z²+h²=(z²+z)p`.

Since `z=a/(1+a)`, multiplying by `(1+a)²` yields the exact pair equation

`(1+h²)a²+ap+h²=0`.

The seed makes `p=w_a²+s w_a` binary-linear in the 17 free source-mask bits.
The implemented pair equation therefore uses **2,227 AND gates per slot**.
The source product has zero constant coefficient, so `p=1` is impossible in
this W18 policy and the transformed equation excludes `a=1`; `h != 0`
excludes `a=0`. These are the exceptional values for this conversion.

For three standard reciprocal coordinates `a,b,c`, the binary third
summation polynomial is `(abc)²+abc=(a+b+c)²`. Odd-degree halftrace turns it
into the exact conditions

`abc + H((a+b+c)²) + epsilon = 0`, `Tr(a+b+c)=0`, `epsilon in GF(2)`.

Seven such links join the eight source-pair outputs to the chosen raw
preimage of the public point. Halftrace, trace, squaring, and Frobenius
rotation are binary-linear; the triple product supplies the nonlinear gates.
The full formula has **189,477 AND gates**, including the exact source BDD.
The construction retains the earlier cross-slot folded-column replay policy:
source pairs are column-distinct inside each slot, while a returned model
must be checked across slots before insertion as a relation.

## Frozen comparison and query

The [protocol](protocol.json) fixes the source and binary hashes, one worker,
600 seconds of solver time, 615 seconds of parent time, and 4 GiB combined RSS.
The target is the earlier fresh ordinary public point
`Q=(1052727368764798954359115163823647684025,
2071227447786120917960296877345506689833)`, workload
`cc09e7eb202a`, using raw preimage index zero. The old and new formulas
use the same fixed seed, W18 support, eight rotations, public point, and
preimage. Formula construction and input writing are outside the bounded
solver interval; all local CPU timings are exploratory without a host-level
isolation receipt.

| Ordinary formula on the same public point | Prior shifted reciprocal | Halftrace-cubic standard reciprocal |
| --- | ---: | ---: |
| Variables | 889,295 | **441,023** |
| CNF clauses | 763,388 | **570,425** |
| Native-XOR rows | 633,524 | **249,569** |
| Total constraints | 1,396,912 | **819,994** |
| XCNF bytes | 29,477,399 | **18,808,935** |
| Ordinary one-worker query | `BOUNDED_UNKNOWN` at 615-second parent cap | `BOUNDED_UNKNOWN` at 615.053-second parent cap |

The [ordinary formula](ordinary.xcnf) has SHA-256
`d4d9d683997b2addbb9a87202e2ca03302ab9a98e52f40c49601952cf94491dd`.
The [query receipt](query_result.json) binds its construction, solver flags,
wall interval, status, and the [raw stdout](solver.stdout.txt) and
[stderr](solver.stderr.txt). The sampled combined peak was **729,366,528
bytes**; the solver had entered search and wrote 1,482 `c rst` rows before
the parent stopped it. The frozen runner's `restart_rows: 798` field counts
`c [` diagnostic rows; the [independent audit](audit_result.json) records the
correct restart count. The prior and new capped rows do not define a
solver-time speed ratio.

## Verification and next gate

The [control receipt](control_result.json) evaluates a complete archived
16-point relation against every clause and native-XOR row in the
[constructed formula](control.xcnf). The separate [verifier](verify.py) scans
both formula files and hashes, independently implements field reduction and
halftrace, checks all eight source-pair equations and seven group links,
reconstructs the source points and folded columns, and finds exactly one
sign assignment whose eight rotated pair sums equal the archived raw target.
Its terminal status is `PASS_INDEPENDENT_N131_HALFTRACE_CUBIC_AUDIT`.

The remaining algorithmic gate is an unpinned ordinary relation under the
same frozen resource envelope. The new local equations expose the useful
next operator: eliminate or generate two still-free pair outputs jointly
from their 17-bit fixed-seed products and the target-dependent halftrace
link, without enumerating the pair-domain Cartesian product. Test that
operator on the frozen N41 public point with source-column replay, then
transfer it to this N131 workload only after its source-bound work and
memory fit the 600-second/4-GiB gate. Verified ordinary relations would then
enter yield, novel-rank, factor-log, and single-target online accounting.

Reproduce the bounded experiment from a fresh copy of this write-once
directory with `python3.12 -B run.py freeze`, `python3.12 -B run.py control`,
`python3.12 -B run.py query`, and `python3.12 -B verify.py`. The Sage-derived
input receipts were generated by the repository's checked Sage launcher;
these four replay commands use only native Python field arithmetic and the
frozen CryptoMiniSat binary.
