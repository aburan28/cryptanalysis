# Exact mixed-rotation all-seed inverse over N41 raw diagonal atoms

The corrected four-atom inverse scanned all **63 nonzero shared mask-XOR
seeds** for the archived N41 raw diagonal-atom source. For the constructed
positive output, its only algebraic seed hit was `s=1`; group replay
recovered the archived masks `(2,3,6,7)` and raw sum
`(278790425788,1531090290805)`. The trace-zero control had no
algebraic or group hit. The measured positive and control query intervals
were **1.527 s** and **1.484 s** after 0.776 s of reusable setup.

This is an exact stage experiment with `candidate_id: null` and
`run_id: null`. The field is `GF(2)[t]/(t^41+t³+1)`, the curve is
`y²+xy=x³+1`, the two Frobenius rotations are 10 and 15, and the
factor-base source is the 32 rational W6 masks in the archived
[diagonal-atom screen](../n41_n131_diagonal_atom_20261010/screen.json).
Each mask has two signed raw points. The 32 masks fold into 26 source
columns; the usable four-atom witnesses require four distinct columns.
The query input is a proposed **raw four-atom sum reciprocal x coordinate**
`z`, with the two values frozen in the
[mixed-rotation input](../n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json).

## Method and measurements

For each source seed `s=a⊕b`, the [sweep](sweep.py) enumerates signed
raw-point pairs with distinct source columns and stores reciprocal x
coordinates of their pair sums after rotations 10 and 15. It solves the
reciprocal S3 quadratic for each left coordinate and proposed `z`, looks
up each root in the right table **within the same seed**, and checks the
four source columns and group sum. The two group hits for the positive
case are the two signs of one x-coordinate witness; one matches the
archived raw and cofactor-four projected points exactly. The
[protocol](protocol.json) binds source and runtime hashes, one worker,
120 seconds per case, 4 GiB RSS, and case order before execution. The
[result](result.json) contains the exact seed sweep, all group hits,
nanosecond intervals, and 268,779,520 B process peak RSS.
An [independent replay](independent_replay.json) used separate bit-field
arithmetic to test all 15,684 coordinate pairs per case directly against
S3, then replayed accepted four-point sums and cofactor-four projections.
It reproduced the single positive seed and empty control.

| Case | Proposed `z` | Seeds tested | Algebraic seed hits | Group hits | Pair-output probes | Query time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Constructed positive | 372259237034 | 63 | `[1]` | 2 signed | 978 | 1.527 s |
| Trace-zero control | 620813031128 | 63 | `[]` | 0 | 978 | 1.484 s |

Setup enumerated 1,956 signed pair states per rotation, reduced to 978
distinct output coordinates per table, in 0.776 s. The positive case
had one pair-coordinate product match; the control had zero. The host
does not have a CPU isolation receipt, so the intervals are stage
diagnostics. The exact seed and group decisions were independently
replayed from the recorded points.

## Source correction and capped SAT gate

The preceding [all-seed comparator](../mixed_fouratom_seed_sat_20261010/allseed.py)
used cofactor-four subgroup atoms from `w6_input.txt`. Its recorded
empty positive set is classified **`PRODUCER_FAILURE_WRONG_POINT_DOMAIN`**.
At mask 2 the archived raw x coordinate is `549755813890`, whereas the
old comparator used subgroup-atom x coordinate `1055159463268`. The
[terminal audit](terminal_audit.json) binds both receipts and retains the
failed row. This correction changes the finite group-domain comparator;
the algebraic SAT formula itself was constructed over raw masks and had
a checked complete positive assignment.

The preceding unpinned-seed N41 SAT positive and trace-zero runs both
ended with raw solver status `s INDETERMINATE` under the frozen 18-second
solver limit. Their audited terminal status is **`CENSORED_TIME`**,
with 18.478 s and 19.672 s parent wall intervals, respectively. Neither
SAT result supplies an ordinary public-point relation. The exact
all-seed sweep shows that a table-backed inverse can resolve this fixed
proposed-output subproblem; it does not supply a way to derive a useful
`z` from the public target.

## Next source-bound gate

The N131 fixed-seed mixed-rotation native inverse has 4,124 coordinates
per table and measured 0.342–0.358 s per proposed output. Multiplying
the lower endpoint by all 16,383 nonzero W14 seeds gives about **5,600 s**
for a literal unpinned sweep, outside the one-worker 600-second gate.
The next experiment must use the public target and the other free blocks
to reject seed families before the pair-output inverse. Its acceptance
test is a complete N41 public-point relation with independent group and
column replay, followed by a frozen N131 resource projection. The
constructed output and the trace-zero control remain correctness and
selectivity checks for that experiment.
