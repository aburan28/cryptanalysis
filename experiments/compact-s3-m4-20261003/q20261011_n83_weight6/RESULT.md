# Q1449: N83 weight six preserves final-link throughput at a fixed API budget

Increasing the four-leaf normal-basis x weight limit from five to six on the
same N83 ordinary public point completed **2,735** distinct final-link checks
in **500,052** counted field-API method entries. The matched weight-five
attempt completed **2,733** checks in **500,136** entries. The descriptive
throughput ratio is **1.0009**. The control produced a model whose three S3
links and four raw leaf weights were replayed independently.

The curve is `EC1N83Ckb1h876c2921cb64`, ordinary workload
`bab50a1e5f66`, with `isogeny: "none"`. Q1449 is a proposal-stage
measurement: the W≤6 projected factor base has not been enumerated, so
actual B, folded K, and its enumerated-set digest remain null. Its
`candidate_id` and `run_id` remain null. The changed variable is the
factor-base weight policy; the public target, raw target preimage coset,
balanced three-link S3 construction, solver binary, branch seed eight,
`satpivot` root encoding, selector early-support cap one, and eager
leaf-rationality policy are fixed against Q1443.

## Measured search stage

The operation unit is one public `CountedOnb` method entry during
`solver.solve`, including failed search. The 500,000-entry stop is checked
after propagator batches, explaining the small overshoot. A fresh process
was used for each row. Control and ordinary work are separate.

| N83 row | Status / stop | Counted API entries | Final-link checks | Exact target S3 matches | Checks per million entries | Solver CPU s | Solver wall s |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| W≤5 Q1443, same target | `BOUNDED_UNKNOWN`; API cap | 500,136 | 2,733 | 0 | 5,464.51 | 15.554 | 97.053 |
| W≤6 Q1449 control | `ALGEBRAIC_MODEL`; pinned fixture | 466 | 1 | 1 | — | 0.008 | 0.012 |
| W≤6 Q1449 ordinary | `BOUNDED_UNKNOWN`; API cap | 500,052 | 2,735 | 0 | 5,469.43 | 16.136 | 22.567 |

The two ordinary rows made 685 and 686 pair-root queries respectively,
and 2,733 and 2,735 final-link rejections. Their field-operation vectors
are retained in [measurements.json](measurements.json). The large difference
in wall time alongside similar CPU time reflects uncontrolled host
conditions; it is not a CPU speedup comparison. The ordinary W≤6 process
reported 170,098,688 peak RSS bytes. The W≤5 row reported 126,304,256.

On this same N83 point, the archived SAT campaign had already charged
8,452,764 API entries. Q1449 adds 500,052, making **8,952,816**
(`2^23.09`) recorded SAT API entries across ordinary attempts. The control
adds no ordinary-target charge. None of these censored attempts estimates
the work for a completed decomposition. In particular, neither a per-solve
`2^x` nor a complete N131 challenge gap can be inferred from the zero-match
rows; both remain null in the receipt.

The separate Q1447 N131 W≤7 pure pair-index model is `2^85.18` logical
actions, 24.18 bits above an abstract `2^61` action cap. That is a
conditional **method model in a different unit**, not a calibration of this
SAT result or an estimate of complete solve work. Its W≤7 base count and
rank yield remain conditional. The matrix proxy there is `2^59.50`
modular events.

## Interpretation and next step

At this API budget, increasing the N83 weight limit by one scarcely changed
the number of target-link checks. The next change should alter how the
solver reaches target-compatible middle pairs, then measure a verified
ordinary relation and the number of distinct, rank-increasing outputs per
query on N53 and N83. This tests the output multiplicity needed by the N131
W≤7 design more directly than another small weight-only search.

The [protocol](protocol.json), [frozen inputs](inputs.json), and
[pre-run source receipt](freeze.json) retain the exact hashes and settings.
CNF/XCNF inputs are addressed by hashes and stored in `/private/tmp`;
regenerate them before replay if those temporary files are removed. The
solver logs are [control.log](control.log) and [ordinary.log](ordinary.log).

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n83_weight6/validate.py
```

The validator rehashes source and inputs, recounts field API entries,
checks the same-target comparison, and replays the control S3 links.
