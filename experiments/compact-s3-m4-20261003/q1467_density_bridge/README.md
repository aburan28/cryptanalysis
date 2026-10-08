# Q1467: density-matched four-point solver gate

Q1467 is a point-decomposition **proposal**, not a complete index-calculus
candidate. Its records use `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. `PDP4hybrid` names the compact chained-\(S_3\) native SAT
stage; it is not a final relation-matrix solver. No complete N131 work
exponent or single-target IC speedup is reported.

## Exact bases and counting scope

| Field/curve ID | Exact base | Actual usable points `B` | Folded columns `K` | Uniform-target four-multiset mean upper bound |
| --- | --- | ---: | ---: | ---: |
| `EC1N53Ckb1hf77aab617904` | first 26 projected columns of the complete W≤3 base | 2,756 | 26 | 0.114473430036 |
| `EC1N83Ckb1h876c2921cb64` | complete W≤4 base | 1,934,066 | 11,651 | 0.241126875147 |
| `EC1N131Ckb1h6816f880945e` | complete W≤6 reference, no solver run | 6,559,634,788 | 25,036,774 | 0.113354289645 |

The N53 selected set and its raw-x mask digest are in
[`n53_w3_26_orbits.json`](n53_w3_26_orbits.json). The immutable input metadata
records the exact base digest for every case. The counting quantity is
`C(B+3,4)/(r-1)`; it bounds the fraction of uniform nonidentity subgroup
targets that can have any four-point representation. It is **not** a measured
yield, an independence assumption, or a solver probability. The N53 and N131
values differ by about 0.0142 bits.

## Frozen solver cells

The six inputs are pinned and unpinned known-solution controls plus ordinary
queries at each degree. Ordinary public targets and workload IDs are reused
from Q1466; the factor-base policy is the controlled change. The input builder
uses three chained \(S_3\) links and does not expand \(S_5\). The
[`solver_protocol.json`](solver_protocol.json) binds the input hashes, Q1466
binary and compile receipt, checked Sage runtime, run order, one-million
conflict cap, 250,000 pair-candidate cap, and 60-second native wall cap.

An initial N53 pinned SAT run used a replay wrapper that passed a clause list
where the verifier expects a clause count. Its unchanged failed receipt and
model are retained in [`runs_v1/n53_planted`](runs_v1/n53_planted), with the
original [`solver_protocol_v1.json`](solver_protocol_v1.json). A separate
replay found its model mathematically valid. The corrected verifier was
committed and frozen as protocol revision 2 **before** the six runs below.

| Cell | Native result | Verified relation | Exact joint checks | Exploratory solver process wall | Peak child RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 planted, leaves pinned | SAT | 1 | 0 | 0.339 s | 69,206,016 B |
| N83 planted, leaves pinned | SAT | 1 | 0 | 0.401 s | 91,717,632 B |
| N53 planted, leaves unpinned | capped | 0 | 49 | 60.675 s | 545,751,040 B |
| N83 planted, leaves unpinned | capped | 0 | 1 | 60.447 s | 430,145,536 B |
| N53 ordinary | capped | 0 | 49 | 60.443 s | 606,175,232 B |
| N83 ordinary | capped | 0 | 1 | 60.528 s | 485,408,768 B |

The independent [`archive_verification.json`](archive_verification.json)
replays both revision-2 SAT models through the complete CNF and curve group
law, verifies four distinct folded columns, and checks all six source-bound
receipts. It also replays the retained revision-1 model. The four capped
cells are censored observations. In particular, the two unpinned planted
targets are **known representable**, so their failures identify a solver
limit under this cap without relying on an assumed ordinary relation rate.

This is a no-go for the frozen Q1467 solver and 60-second cap. It does not
prove that either ordinary target lacks a decomposition, nor does it bound a
different target-guided solver. With one ordinary query per field and no
verified ordinary relation, natural relation yield, useful-row cost, growth
rate, matched pair-table comparison, and a complete N131 \(2^x\) remain
unknown. The challenge gate remains closed.

## Reproduce and continue

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info
python3 experiments/compact-s3-m4-20261003/q1467_density_bridge/freeze_solver_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1467_density_bridge/build_inputs.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1467_density_bridge/verify_archive.py --check
python3 experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The next measurement should use a complete N53 pair-sum oracle over the
2,756-point base (3,799,146 unordered pairs) to label a preregistered
ordinary-target panel as representable or absent and provide exact witnesses.
Compare the compact solver and a matched pair-table on those **same**
targets, with setup and query costs separately charged. At N83, first recover
an unpinned known-solution control before using ordinary runs to estimate
successful decomposition cost. Preserve all failures and rank measurements;
do not fit a degree-131 solve exponent from capped cells.
