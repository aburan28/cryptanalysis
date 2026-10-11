# One-leaf anchoring leaves the N41 cubic public search capped

Fixing the first W6 source mask to **63**, a value from an independently
replayed eight-point relation on the frozen N41 public point, yields a
**satisfiable** 12,554-variable cubic XCNF. Its complete known assignment
passes all **23,255 clauses and 4,744 native-XOR rows**. CryptoMiniSat entered
search but returned no model before the frozen 30-second solver cap plus a
two-second parent margin. This is a direct feasibility test for splitting the
ordinary search into 32 single-leaf branches: even the certified positive
branch did not clear its allotted time.

The exact instance is `GF(2)[t]/(t^41+t^3+1)` on `y²+xy=x³+1`, public point
`Q=(1458168294740,1672312028033)`, and the same four W6 pair windows at
rotations `0,10,20,30` as the [transported cubic circuit](../n41_transport_cubic_s8_20261011/RESULT.md).
Its source has 32 rational masks per window, **B=256** usable factor-base
points before folding, and **K=26** signed-Frobenius columns. All four raw
preimages of the transported public point remained available. Only the first
source mask was fixed; the other seven masks, pair and middle outputs, and
group branches were free. The known full relation was used only to certify
that this anchored formula has a solution.

| Frozen positive-branch screen | Result |
| --- | ---: |
| Source mask condition | first mask = 63, six unit clauses |
| Formula | 12,554 variables; 23,255 clauses; 4,744 native-XOR rows; 625,991 bytes |
| Solver | CryptoMiniSat5, one worker, `--xor=0`, random seed `20261011` |
| Search receipt | `BOUNDED_UNKNOWN`, parent stop at **32.026 s** solver wall |
| Search activity | **685** restart rows; last logged conflict count approximately **269,000** |
| Combined sampled peak RSS | **87,982,080 bytes**, below the 4-GiB cap |
| Independent assignment audit | **PASS**, all 27,999 formula records |

The [protocol](protocol.json) bound the source, solver binary, public point,
positive anchor, eight prespecified public-screen anchors, and resource caps
before execution. Its stop rule allowed the eight public branches only if the
certified positive branch returned a model inside 30 seconds. The
[screen receipt](screen_result.json) records `STOP_AFTER_CONTROL`; no public
anchor was run. The [case receipt](control.result.json), [formula](control.xcnf),
and [raw solver log](control.stdout.txt) preserve the bounded search. The
independent [verifier](verify.py) rebuilt the frozen circuit, checked source
and output hashes, and evaluated the known relation against every clause and
native-XOR row; its [audit](audit.json) also confirms active search and the
parent stop. CPU wall intervals are exploratory on this unisolated host.

This result narrows the next method choice. Branching on one source leaf does
not by itself make the public-point cubic circuit tractable even when that
branch contains a verified relation. The next N41 experiment should propose
pair or block outputs from the **actual public target constraint** while two
or more pair domains remain free, count exact early rejections, and replay an
unpinned row. A corresponding N131 method needs a source-bound 600-second,
4-GiB work and memory projection before another ordinary query. This local
screen retains `candidate_id: null`; it changes no relation-yield, rank, or
single-target timing record.

Reproduce the frozen diagnostic in a fresh directory with
`python3 -B probe.py freeze`, `python3 -B probe.py run`, and
`python3 -B verify.py`. The producer refuses to overwrite its receipts.
