# Q1421: work-counted exact-root search on ordinary N53/N83 queries

Q1421 compares two decision policies on the identical archived Q1420
balanced-S3 CNFs: CaDiCaL default and an external callback that selects the
first unassigned leaf bit positively before allowing ordinary auxiliary
decisions. The exact S3 root clauses, field arithmetic, formula, targets,
curves, and factor bases otherwise match Q1420. The leaf-first policy is a
branching choice, so it cannot remove satisfying assignments. CaDiCaL's
synchronous terminator stops at 60 seconds and prints counters; the Python
runner retains a separate 75-second process safeguard. Both policies have a
one-million-conflict cap.

The [protocol](protocol.json) fixes all eight cells before solver runs:
`free_mids` known-witness controls and unpinned ordinary queries at each of
N53 and N83 under both policies. The exact Q1301 N53 W≤3 base has
`B=24,062`, `K=227`, curve `EC1N53Ckb1hf77aab617904`. The exact Q1325
N83 W≤5 base has `B=30,977,592`, `K=186,612`, curve
`EC1N83Ckb1h876c2921cb64`. Base-set digests and parent CNF/model hashes
are in the protocol. Each stage has a distinct `PS1...PDP4theory...` ID;
the complete IC `candidate_id` stays null and `isogeny` is `none`.

The primary question is whether leaf-first search reaches useful exact-root
propagation and a verified ordinary relation within the frozen cap. A
known-witness result is only a correctness control. One ordinary query per
degree is a method gate, not a natural-yield estimate. Every failure, cap,
operation count, raw solver transcript, memory measurement, and verified
model is retained. An ordinary N83 relation, if found, needs a separate
checked-Sage replay before promotion. No complete degree-131 `2^x` is
estimated from these eight stage cells; target-dependent formula build,
natural useful-row yield, final matrix solve, descent, and replay remain
separate terms. CPU wall times here are exploratory without a host isolation
receipt.

## Reproduction

All Sage jobs use the repository's checked launcher. On this host, first
rebuild the pinned native binary, then verify the frozen protocol and archive:

```sh
python3 experiments/compact-s3-m4-20261003/q1421_work_counted/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1421_work_counted/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1421_work_counted/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1421_work_counted/verify_archive.py --require-complete --emit
```

Each frozen cell is run by `run_stage.py --degree N --cell CELL --policy
POLICY` through the same checked launcher. The exact run order is stored in
`protocol.json`; the runner refuses to overwrite existing results.
