# Q1426: symbolic second-pair S3 gate

Q1425 computes exact partner roots only after a pair intermediate and one
complete sparse leaf are chosen. Its ordinary N53/N83 runs used the cap on
hundreds of thousands of reverse-root calls without a relation. Q1426 adds
all binary equations of `S3(leaf2, leaf3, mid1)=0` to the formula before
search. The link uses the existing factored three-product circuit and
XOR-to-CNF Tseitin encoding. The Q1425 external root propagator remains
active as a redundant exact check and may still add clauses.

For a fixed `mid1`, this equation is quadratic in the two leaf coordinates
over the normal-basis bits. The hypothesis is that SAT can learn from those
shared equations before completing and root-testing individual leaves. The
added equation is identical to the second pair's mathematical S3 relation,
so it does not remove a valid four-point decomposition. Any SAT model must
also satisfy the archived CNF, the new symbolic link, both exact pair-root
checks, the final target link, and an independent exact-base group replay.

The [frozen protocol](protocol.json) pins one `free_partner` known-witness
control and one ordinary unpinned public target at each of N53 and N83.
Each cell is matched to Q1425's `reverse_target` policy on the same curve,
base, public point, target-preimage list, workload ID, and solver limits.
The Q1426 CNF differs by the new pair link. The curves are
`EC1N53Ckb1hf77aab617904` and `EC1N83Ckb1h876c2921cb64`; actual
usable base sizes before folding are `B=24,062` and `B=30,977,592`, with
folded column counts `K=227` and `K=186,612`. Enumerated-set digests live
in the protocol. The stage uses `PS1...PDP4theory...`, `candidate_id` is
null, and `isogeny` is `none`.

The frozen limits are one million CaDiCaL conflicts, 60 internal seconds,
and a 75-second outer safeguard. The known-witness cells are correctness
controls, not natural relation-yield samples. Ordinary failures and caps
remain censored rows. The host is not isolated, so CPU walls are
exploratory. A verified ordinary relation is a point-decomposition gate,
not a complete IC result or a degree-131 `2^x` estimate.

## Frozen results

The [four-cell archive](verification.json) passes exact CNF reconstruction,
model checks, and independent group replay for both SAT controls. Both
ordinary cells reached the 60-second internal cap without a relation:

| Degree | Cell | Status | Verified relations | Solver process seconds, exploratory | Reverse pair-1 calls | Accepted reverse partners |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 53 | Freed-partner control | SAT | 1 | 0.637 | 1 | 1 |
| 53 | Ordinary target | Censored | 0 | 60.265 | 1,080,547 | 0 |
| 83 | Freed-partner control | SAT | 1 | 0.186 | 1 | 1 |
| 83 | Ordinary target | Censored | 0 | 60.346 | 485,107 | 0 |

On the matched ordinary targets, the Q1425 comparator also capped at 60
seconds without a relation. Q1426 made 1,080,547 versus Q1425's 985,233
reverse pair-1 calls at N53, and 485,107 versus 569,521 at N83. The
corresponding raw field-operation triples `(mul, square, inverse)` are
`(31,537,100, 178,516,070, 2,186,139)` versus
`(28,772,804, 162,883,486, 1,995,497)` at N53 and
`(23,771,216, 202,783,510, 1,940,534)` versus
`(27,904,433, 238,040,600, 2,277,849)` at N83. These are
**partial raw counts**, not calibrated equivalent operations. Peak child
RSS was 1,398,865,920 bytes at N53 and 520,339,456 bytes at N83; full
receipts retain all counters and failure outcomes. The new symbolic link
did not get the ordinary search past sparse reverse-partner rejection.

There is no measured natural relation yield, cost per useful row, or
degree-131 complete-solve `2^x` from these censored cells. The next method
needs target-conditioned pair-sum feasibility or witness generation that
changes this rejection pattern; adding the pair equation to SAT alone did
not do so in this frozen test.

## Reproduction

Use the checked repository Sage launcher for every Sage job:

```sh
python3 experiments/compact-s3-m4-20261003/q1425_reverse_pair/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/run_stage.py --degree 53 --cell free_partner
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/run_stage.py --degree 53 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/run_stage.py --degree 83 --cell free_partner
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/run_stage.py --degree 83 --cell ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1426_symbolic_pair/verify_archive.py --require-complete --emit
```

Run all four cells in protocol `run_order`. The runner refuses to overwrite
a row. The protocol and source hashes are committed before ordinary runs.
