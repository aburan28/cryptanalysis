# Q1463: ordinary N53/N83 four-point WDSat search measurements

The Q1460 shared-prefix encoding now runs against the archived ordinary
four-point queries at N53 and N83. It lowers every CNF clause to width at
most four with 268 and 160 added variables respectively, retaining the
original 795 and 1,245 native XOR rows. Both plain WDSat and WDSat with
XOR-Gauss entered search on each exact point. All four runs reached their
120-second wall caps with status `BOUNDED_UNKNOWN`; the observed verified
relation count is zero for these capped attempts. The receipts preserve the
CPU work performed and memory peak, including failed attempts.

| Field | Curve ID | Actual base B | Folded columns K | Solver | Status | Wall cap / elapsed, s | User CPU, s | Peak child RSS, MiB |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| N53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | plain | `BOUNDED_UNKNOWN` | 120 / 120.02 | 92.32 | 223 |
| N53 | same | 24,062 | 227 | XOR-Gauss | `BOUNDED_UNKNOWN` | 120 / 120.04 | 9.69 | 264 |
| N83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | plain | `BOUNDED_UNKNOWN` | 120 / 120.02 | 17.87 | 857 |
| N83 | same | 30,977,592 | 186,612 | XOR-Gauss | `BOUNDED_UNKNOWN` | 120 / 120.03 | 14.01 | 1,351 |

These are one-query point-decomposition measurements on frozen public
targets, with workload IDs `74f2979b3e68` (N53) and `bab50a1e5f66` (N83).
The factor-base set digests and original Q1410/Q1408 source archive hashes
are in `freeze.json`. The transformation is bound to Q1460's equivalence
check and pinned compiled solver receipt. `validate.py` independently checks
every run's exact source, executable, output bytes, search markers, and
status. No local Sage job was launched for these XCNF runs.

The CPU/wall ratios range from about 0.08 to 0.77 on this contended macOS
host, so these runs do not rank plain against XOR-Gauss by elapsed time.
The four statuses are censored observations, not a natural-query yield
estimate or a solved-work exponent. `candidate_id` and `run_id` remain null
because this is a point-decomposition stage proposal, Q1463, rather than a
fully specified IC pipeline. The exact stage code is `PDP4sat` and
`isogeny` is `none`.

## Distance to the N131 challenge

The best separately quantified Q1462 W≤7 full pair-index model remains
`2^86.1847` **counted pair-add attempts**, 25.1847 bits above an abstract
`2^61` pair-add reference under its sampled-base and optimistic rank-yield
assumptions. Its index construction alone is `2^64.53` states. Q1447's
conditional final-matrix proxy is `2^59.50` modular events in a different
operation unit. The full N131 one-target solve exponent and challenge gap
remain `null`: Q1463 supplies no completed ordinary PDP cost or measured
relation yield to combine with setup, rank growth, matrix work, and target
handling. `analysis.json` records these distinctions as machine-readable
fields.

## Next measured improvement

The next search should record WDSat's branch/conflict count and CPU time at
checkpoints, then compare CNF width-three versus width-four encodings and
plain versus XOR-Gauss on these same two ordinary archives with a fixed CPU
work cap. The present wall cap delivered 9.69 to 92.32 user CPU seconds,
which prevents a fair hyperparameter ranking. Retain every censored cell
and verify any returned model first against both XCNFs, then against the
curve group law and exact factor base. A completed ordinary relation and
its cost would make the first calibrated per-decomposition extrapolation
possible; multi-output relation enumeration and rank novelty are needed to
test Q1447's more favorable W≤7 query regime.

## Reproduce

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_ordinary/validate.py
python3 experiments/compact-s3-m4-20261003/q20261011_wdsat_ordinary/analyze.py
```

Each `run.py` invocation is one previously frozen cell. The existing run
receipts and archived outputs allow validation without repeating a capped
search.
