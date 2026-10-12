# Q1465: width-three versus width-four WDSat encoding screen

The width-three shared-prefix construction is equivalent to the original
balanced-S3 XCNF and works in the pinned WDSat solver. Exact prefix OR
definitions preserve the original variable IDs and native XOR rows. An
exhaustive small-clause check covered original widths four through eight,
and the archived N53/N83 full-lock assignments extended to satisfying
models of the new formulas. Three full-lock WDSat cells returned models
independently replayed against both encodings; N83 XOR-Gauss was censored
before search at its 90-second wall cap.

The new ordinary cells use the same public points, curve IDs, actual usable
base sizes, folded columns, base digests, original XCNFs, variants, and
16,384-branch stop as Q1464. All four entered search and reached the branch
cap with status `BRANCH_CAP_REACHED`.

| Field | Solver | Width-three aux vars | Width-three rows | Width-three user CPU, s | Width-four user CPU, s | Width-three / width-four CPU |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| N53 | plain | 708 | 102,979 | 0.758 | 0.776 | 0.977 |
| N53 | XOR-Gauss | 708 | 102,979 | 8.827 | 4.591 | 1.923 |
| N83 | plain | 320 | 192,133 | 1.116 | 1.091 | 1.023 |
| N83 | XOR-Gauss | 320 | 192,133 | 12.891 | 12.227 | 1.054 |

For comparison, width four used 268 auxiliary variables and 101,927 rows
at N53, and 160 auxiliary variables and 191,813 rows at N83. Width three
added 440 and 160 more variables respectively. Its plain results were
within 2.3% of width four in opposite directions, while its XOR-Gauss
totals were higher in both fields. These are single-run, unisolated host
measurements of total solver CPU to the same branch cap. The branch count
omits propagation and Gaussian row work, and a fixed-branch result does not
measure the work to return a natural relation. The source-bound rows and
peak child RSS values are in `analysis.json`.

The width-four plain setting remains the best measured option for a deeper
branch-budget search under this stage metric. The Q1462 conditional N131
W≤7 full pair-index reference remains `2^86.1847` counted pair-add
attempts, 25.1847 bits above an abstract `2^61` pair-add reference. The
fully charged N131 solve exponent and gap remain null pending completed
ordinary decompositions, verified relation yield and rank, matrix work,
target handling, and unit conversion.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_width3/validate.py
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_width3/analyze.py
```

Q1465 is a `PDP4sat` stage proposal with `isogeny: "none"`. Its
`candidate_id` and `run_id` remain null pending a complete IC pipeline.
