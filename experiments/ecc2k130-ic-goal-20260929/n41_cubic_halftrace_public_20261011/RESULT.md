# Halftrace-cubic public-point N41 circuit

An exact halftrace-cubic decomposition circuit cuts the frozen N41 public-point formula from **72,710 to 11,645 AND gates**, while retaining the twelve source positions, distinct-column rule, seed coupling, and public-target equation. The new formula is 1,217,889 bytes, **83.7% smaller** than the basis-aware quartic comparator. Its known twelve-point relation satisfies every clause and native-XOR row. The unpinned one-worker query ran to its 60-second CryptoMiniSat cap with status `BOUNDED_UNKNOWN`.

## Algebra and construction

For reciprocal x coordinates `a`, `b`, and `c` of a three-point sum, write `z=abc`. The usual binary S3 equation is

`z²+z=(a+b+c)²`.

In the odd-degree field, `H(v)²+H(v)=v+Tr(v)` for the halftrace `H`. Thus S3 is exactly the conjunction

`abc + H((a+b+c)²) + epsilon = 0`, `Tr(a+b+c)=0`, `epsilon in GF(2)`.

Halftrace, squaring, and trace are binary-linear maps. Only the triple product needs nonlinear gates. At each source pair, `a` and `b` lie in the six-dimensional rotated reciprocal-coordinate span. Their product is retained as eleven sparse diagonal basis images, so multiplying it by the proposed pair output costs 451 bilinear gates per pair. The formula has six source-pair links, three links joining pairs into four-point blocks, and two links joining the blocks to the chosen raw preimage of the public point. The source points are the raw cofactor-four lifts; the public input and source-column rules are identical to the comparator.

The [protocol](protocol.json) freezes `GF(2)[t]/(t^41+t³+1)`, curve `y²+xy=x³+1`, curve ID `EC1N41Ckb1h023d9a38bbf7`, public point `(1458168294740,1672312028033)`, six rotations `0,5,10,15,20,25`, 384 usable projected source points, 26 folded columns, two raw-target reciprocal lifts, one worker, 120 seconds for formula construction, 60 seconds for CryptoMiniSat with five seconds of parent drain, and 4 GiB combined RSS. The source and solver hashes were frozen before the control and query. The complete IC pipeline remains a design proposal with `candidate_id: null`.

## Exact formula and bounded search

| Same N41 public point and source law | Basis-aware quartic | Halftrace-cubic |
| --- | ---: | ---: |
| AND gates | 72,710 | **11,645** |
| Variables | 109,913 | **19,154** |
| CNF clauses | 224,831 | **41,776** |
| Native-XOR rows | 36,843 | **7,015** |
| XCNF bytes | 7,468,648 | **1,217,889** |
| Unpinned public query at 60-second solver cap | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |

Of the new AND gates, 216 form the six source-pair product vectors, 2,706 multiply those vectors by proposed pair outputs, and 8,723 implement the five joint S3 links. The [control](control_result.json) checks all 41,776 clauses and 7,015 native-XOR rows under the archived twelve-point public relation. The [independent source-pair audit](audit_result.json) checks both relative signs of every one of 496 unordered mask pairs at each of six rotations: all **5,952** group sums satisfy the original S3 equation, zero trace, and one of the two halftrace branches. An additional fixed-seed 1,000-triple differential check compared the cubic predicate to the original S3 equation for arbitrary field coordinates.

The [query receipt](query_result.json) records 1.0694 seconds of formula construction, 0.0115 seconds to write and hash the formula, and 65.0346 seconds in the bounded solver process, totaling 66.1154 seconds. Combined sampled RSS peaked at 100,630,528 bytes. The solver produced 411 restart rows and no terminal SAT/UNSAT line before the parent stopped it. These wall intervals are exploratory on an unisolated host. The [terminal audit](terminal_audit.json) rebuilt the exact formula, checked its SHA-256 and byte count, verified the input lock and phase sum, and inspected both compressed solver logs.

The next integration gate is an eight-slot N131 W18 circuit with four sparse source-pair links and a three-link public sum tree. Its source masks must be restricted to the 131,307 rational W18 seeds per rotation, and its folded-column policy must be enforced or checked exactly. Freeze a known relation as a full-assignment control, measure the complete source-bound formula and memory against the one-worker 600-second/4-GiB boundary, then run one ordinary public point if that construction gate passes. A verified public relation would feed the relation-yield, rank, factor-log, and same-point one-target timing stages.

Reproduce the frozen audit with `python3.12 -B experiments/ecc2k130-ic-goal-20260929/n41_cubic_halftrace_public_20261011/verify.py`. The [runner](run.py) implements `freeze`, `control`, and `query`; the [circuit](circuit.py) contains the exact source-pair and joint-link encoding.
