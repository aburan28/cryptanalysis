# Unpinned N41 mixed-rotation four-atom SAT gate

An exact XCNF for two mixed-rotation raw diagonal-atom pairs admits a
complete constructed positive assignment with **3,660 variables, 6,283
CNF clauses, and 1,638 native-XOR rows**. The four W6 source masks, their
two pair-output coordinates, and the shared source seed are free solver
variables. A 20-second parent gate gave raw solver status
`s INDETERMINATE` for both the constructed positive and trace-zero
control, so the terminal classification for each is `CENSORED_TIME`.
The complete assignment check establishes formula correctness for the
archived positive witness; the capped solver rows measure search behavior.

This is a stage experiment on `EC1N41Ckb1h7d5e80d3c4d0`, over
`GF(2)[t]/(t^41+t³+1)`, with rotations 10 and 15, 32 rational source
masks, and 26 folded source columns. The protocol records a 384-point
full base, one worker, 4-GiB RSS cap, solver flags, source hashes, and
case order. `candidate_id` and `run_id` remain `null` for this component.

The [circuit](circuit.py) encodes raw reciprocal mask inputs, valid-mask
and four-column conditions, the six-bit shared XOR seed, two bilinear
pair-output equations, and the reciprocal S3 equation for a proposed
four-atom sum coordinate `z`. The [freeze step](freeze.py) generated
the [positive](n41_positive.xcnf) and
[control](n41_trace_zero_control.xcnf) formulas before the
[solver run](run.py). The positive witness from the archived
mixed-rotation input satisfies every clause and native-XOR row.

| Case | Proposed `z` | Variables / clauses / XOR rows | Parent wall | Solver peak RSS | Raw status | Terminal status |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Constructed positive | 372259237034 | 3,660 / 6,283 / 1,638 | 18.478 s | 48,447,488 B | `INDETERMINATE` | `CENSORED_TIME` |
| Trace-zero control | 620813031128 | 3,657 / 6,283 / 1,635 | 19.672 s | 126,943,232 B | `INDETERMINATE` | `CENSORED_TIME` |

The [frozen protocol](protocol.json), [result](result.json), raw solver
stdout, stderr, formulas, and checked [Sage runtime](sage_runtime_info.json)
retain the exact gate. The result producer's `EXITED_WITHOUT_STATUS` label
did not parse CryptoMiniSat's `s INDETERMINATE` line; the
[terminal audit](../n41_mixed_fouratom_seed_sweep_20261010/terminal_audit.json)
uses that raw line and the frozen solver time limit to classify both rows.

The initial [all-seed comparator](allseed.py) used cofactor-four subgroup
atoms as its group inputs, while the XCNF and constructed control concern
raw diagonal atoms. Its empty-positive receipt is preserved in
[seed_result.json](seed_result.json) and classified
`PRODUCER_FAILURE_WRONG_POINT_DOMAIN` by the same terminal audit. The
[corrected exact sweep](../n41_mixed_fouratom_seed_sweep_20261010/RESULT.md)
uses the archived raw source and finds the constructed seed-one witness
in 1.527 s of query time. Its direct bit-field replay checks all 15,684
coordinate pairs per case. A public-target relation gate needs a way to
derive useful proposed `z` values and eliminate seed families before
this inverse stage reaches the N131 width.
