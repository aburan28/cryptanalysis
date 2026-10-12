# Q1464: fixed-branch WDSat work probe on ordinary N53/N83 queries

An instrumented, pinned WDSat build now reports power-of-two checkpoints for
each upstream `conf[0]++` left-branch site and stops at exactly 16,384 such
attempts. On the same frozen Q1463 ordinary N53 and N83 formulas, both plain
and XOR-Gauss reached that work cap after entering search. This supplies a
comparable branch-count boundary even while the host's wall time varies
widely.

| Field | Curve ID | Actual base B | Folded K | Solver | Counted left branches | Total user CPU, s | Wall, s | Peak child RSS, MiB | Status |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| N53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | plain | 16,384 | 0.776 | 7.40 | 220 | `BRANCH_CAP_REACHED` |
| N53 | same | 24,062 | 227 | XOR-Gauss | 16,384 | 4.591 | 16.97 | 307 | `BRANCH_CAP_REACHED` |
| N83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | plain | 16,384 | 1.091 | 1.62 | 858 | `BRANCH_CAP_REACHED` |
| N83 | same | 30,977,592 | 186,612 | XOR-Gauss | 16,384 | 12.227 | 20.28 | 1,349 | `BRANCH_CAP_REACHED` |

At this cap the total user CPU for XOR-Gauss was 5.91 times plain at N53
and 11.21 times plain at N83. These totals include startup and propagation,
which the branch counter does not enumerate. Both variants remained without
a model at the fixed cap, so the ratio measures stage cost at equal counted
branches, not the work needed to find a relation. The results have one run
per cell on an unisolated host; `analysis.json` retains the precise values.

The four full-lock controls used Q1460's exact archived inputs. N53 plain,
N53 XOR-Gauss, and N83 plain returned models replayed against both their
transformed and original XCNFs. N83 XOR-Gauss reached its 90-second wall cap
after 9.227 user CPU seconds, before the search marker; its status is
`CENSORED_BEFORE_SEARCH`. The same N83 XOR-Gauss binary later entered search
and reached the branch cap on the ordinary input. The control and ordinary
statuses are retained separately.

An initial replay implementation reparsed the original XCNF header for each
model variable. Its two completed N53 control receipts, the interrupted N83
control's solver output, original runner source, and interruption receipt are
preserved under `runs/pre_fix/` and `pre_fix_incident.json`. The corrected
runner parses that header once. All primary Q1464 runs use the corrected
source hash, and `validate.py` checks both the primary receipts and the
preserved incident.

## Work ledger and next gate

The fixed branch metric counts four instrumented left-branch sites in WDSat.
It does not count Boolean propagation, Gaussian row work, field operations,
factor-base construction, relation checks, rank increments, matrix work, or
target descent. The Q1462 conditional N131 W≤7 full pair-index reference is
still `2^86.1847` counted pair-add attempts, 25.1847 bits above an abstract
`2^61` pair-add reference. The fully charged N131 solve exponent and gap
remain null because no ordinary decomposition cost or relation-yield law has
been established from these capped searches.

The next solver search should compare width-three and width-four shared-prefix
CNF encodings on these exact ordinary inputs under a larger fixed branch
budget, reporting both branch count and total CPU. Any returned model needs
independent XCNF and curve group-law replay, followed by rank-novelty and
multi-output relation measurements. This is the evidence needed to begin a
degree-131 decomposition growth fit and a complete-pipeline projection.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_workprobe/validate.py
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_workprobe/analyze.py
```

The proposal ID is `Q1464`, with `PDP4sat`, exact curve/base/workload
identities, `isogeny: "none"`, and null `candidate_id` and `run_id` pending
a complete IC pipeline.
