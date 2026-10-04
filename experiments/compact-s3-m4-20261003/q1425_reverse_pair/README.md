# Q1425: exact reverse S3 partner roots

Q1424 spent its ordinary N53 and N83 caps generating tens or hundreds of
thousands of complete leaf pairs, depending on decision order. Q1425 adds a
sound reverse condition: after a pair intermediate `m` and one nonzero leaf
coordinate `a` are fixed, symmetry of `S3` gives at most two partner
coordinates `b`. The external propagator computes those exact roots and
discards `b=0`, coordinates above the normal-basis weight bound, and
coordinates that cannot lift to the curve. It emits guarded clauses for the
remaining roots. For `m=0`, `S3(a,b,0)=a²b²+1`, so `b=a⁻¹`. The existing
forward pair-root, leaf-lift, final-root, and full-model checks remain.

The [frozen protocol](protocol.json) has two policies: `reverse_target`
decides target selector, leaf0, leaf1, both intermediates, leaf2, leaf3;
`reverse_mid` decides selector, both intermediates, leaf0, leaf2, leaf1,
leaf3. Each policy uses one `free_partner` known-witness control and one
ordinary public target at each degree. The control starts from Q1420's
`full_lock` archived CNF, removes exactly the leaf1 and leaf3 unit pins,
and checks the reconstructed CNF byte for byte. Its known witness is a
correctness control; it measures no natural relation yield. Ordinary cells
are matched to Q1424 on the same unpinned CNF, public target, factor base,
and caps: one million conflicts, 60 seconds internally, 75 seconds outside.

The curves are `EC1N53Ckb1hf77aab617904` and
`EC1N83Ckb1h876c2921cb64`. The actual usable factor-base sizes before
folding are `B=24,062` (folded `K=227`, N53, W≤3) and `B=30,977,592`
(folded `K=186,612`, N83, W≤5). Base digests and exact target values are
in the protocol. Stage IDs use `PS1...PDP4theory...`; `candidate_id` is null
because this is not a complete IC pipeline, and `isogeny` is `none`.

## Reproduction and claim boundary

Use the repository's checked Sage launcher for every Sage job:

```sh
python3 experiments/compact-s3-m4-20261003/q1425_reverse_pair/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/run_stage.py --degree 53 --cell free_partner --policy reverse_target
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/run_stage.py --degree 53 --cell ordinary --policy reverse_target
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/verify_archive.py --require-complete --emit
```

Run all eight cells in `run_order` for a complete archive. The runner refuses
to overwrite a row. Preserve failures, timeouts, field operation counts,
memory, and raw solver output. A verified ordinary relation would establish
one successful point-decomposition attempt at that degree only. An ordinary
cap without a relation is censored, not a proof of nonrepresentability.
CPU wall times on this host are exploratory. Complete relation collection,
natural yield, useful rank, matrix work, target descent, scalar replay, and
the degree-131 `2^x` total remain unknown at this stage. No below-`2^61`
claim follows from a solver-only result.
