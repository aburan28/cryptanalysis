# Q1436: exact affine feasibility for a partial sparse pair

Q1435 enumerated both leaves' sparse completions after they had one or two
normal-basis weight units left. Q1436 uses the fact that for fixed first leaf
`a` and intermediate `m`, `S3(a,b,m)` is **affine over F2 in `b`**. It
enumerates every weight-allowed completion of the cheaper leaf when its slack
is at most two, then solves the other leaf's free coordinates as an exact
binary linear system. A unique solution is checked against the other leaf's
weight bound. An inconsistent system or a unique overweight solution excludes
that first-leaf completion. A consistent rank-deficient system is retained as
unknown. Thus a zero-feasible result soundly excludes a sparse pair; a unique
result can force both leaves. This avoids enumerating the Cartesian product
of both sparse domains. Q1436 checks states with up to 18/24 free bits per
leaf at N53/N83, four bits earlier than Q1435's window. Its work cap is
8,192 affine columns per state.

The [49-case validation](affine_validation.json) compares the native result
with direct Sage `S3` enumeration on archived ordinary zero trails, synthetic
states, and nine known-witness cases. It found 40 zero-solution cases and
retained all nine witnesses. The [frozen v2 protocol](protocol.json) was
committed before any v2 runs. The first v1 N53 control had a malformed JSON
report after a verified relation; its source, protocol, receipt and diagnosis
are preserved under [failed_v1](failed_v1/README.md). The v2 change only
closed the final JSON array.

| Degree | Curve ID | Actual usable base points `B` | Folded columns `K` | Enumerated-set SHA-256 |
| --- | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | 24,062 | 227 | `05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5` |
| 83 | `EC1N83Ckb1h876c2921cb64` | 30,977,592 | 186,612 | `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8` |

This is proposal `Q1436`, with `candidate_id: null` and `isogeny: "none"`.
Its `PS1...PDP4theory...` identifiers label solver stages, not complete
`IC1` pipelines. Both public targets, workload IDs, CNFs, target preimages,
decision policy, and 60-second/one-million-conflict caps match Q1435.

## Frozen result

Both known-witness controls returned independently verified four-point
relations. Both unpinned ordinary queries reached the 60-second wall cap
without a relation. The [archive verifier](verification.json) independently
replayed each returned model, four sampled span rejections and four sampled
affine zero claims per ordinary degree. Its affine replay constructs columns
from direct Sage `S3` evaluations and solves them with Sage GF(2) matrices.
It does not independently replay every emitted clause. CPU wall times are
exploratory because this host lacks an isolation receipt.

| Ordinary query | Span checks / rejects | Affine checks / zero | Enumerated-leaf options / affine columns | Affine XORs | Total field mul / sqr / inv | First-pair root calls | Peak child RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 396,185 / 279 | 395,906 / 395,906 | 7,703,366 / 138,660,588 | 1,335,395,670 | 3,479,748 / 3,287,430 / 25,537 | 1 | 1,207,648,256 bytes |
| N83 | 75,732 / 207 | 75,525 / 75,525 | 1,894,473 / 45,467,352 | 571,525,667 | 1,449,167 / 6,757,294 / 61,699 | 1 | 543,883,264 bytes |

All affine-tested first-leaf completions in these prefixes had inconsistent
linear systems. No unique ordinary completion or full second-pair assignment
occurred. The first archived affine zero claims have 18/24 free bits on
*each* leaf, versus Q1435's 14/20-bit trigger. The earlier exact rejection
is real, but it does not make the solver leave its first completed first
pair within the cap. Q1436 spends substantially more XOR work than Q1435
on different censored prefixes. The search paths and host contention differ,
so the receipts do not establish a controlled wall-time ratio.

The ordinary rows are lower bounds on unsuccessful attempts. They do not
measure a successful decomposition cost, natural relation yield, useful-row
rate, or the complete N131 `2^x`. The [work ledger](../work_ledger.json)
keeps those values null. Q1414's exact-base uniform-query model requires
less than `2^33.36` abstract work units per query under a complete `2^61`
budget even if every other phase is free. Q1436 supplies no evidence that a
successful N131 query meets that necessary ceiling. No challenge run is
admitted.

## Next method gate

This filter is conditional on a *fixed* pair intermediate and a nearly
determined first leaf of the second pair. The current decision order fixes a
first pair, derives the target-linked intermediate, then explores many
second-pair partial assignments. Progress now requires a compact procedure
that decides or witnesses **global sparse-pair support for the target-linked
intermediate** without walking all those partial assignments or storing the
full quotient-pair index. A verified ordinary N53 relation is the first
test, and a verified ordinary N83 relation on the exact Q1325 base is the
decisive stage gate. Fresh ordinary-query yield and rank measurements would
then precede a fully charged N131 projection.

## Reproduction

From this repository checkout, use the checked Sage launcher for every Sage
job:

```sh
python3 experiments/compact-s3-m4-20261003/q1436_affine_pair/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1436_affine_pair/validate_affine.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1436_affine_pair/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1436_affine_pair/verify_archive.py --require-complete --emit
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The checked Sage runtime receipt was saved before the measured cells.
`run_stage.py` refuses to overwrite an archived run.
