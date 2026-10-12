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
python3 experiments/compact-s3-m4-20261003/q1425_reverse_pair/build_binaries.py --rebuild
python3 experiments/compact-s3-m4-20261003/q1425_reverse_pair/build_binaries.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/run_stage.py --degree 53 --cell free_partner --policy reverse_target
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/run_stage.py --degree 53 --cell ordinary --policy reverse_target
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1425_reverse_pair/verify_archive.py --require-complete --emit
python3 experiments/compact-s3-m4-20261003/q1425_reverse_pair/screen_pair_support.py --check
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

## Frozen outcomes

The [archive verifier](verification.json) checked all eight cells. All four
`free_partner` controls returned independently verified exact-base relations,
and both reverse gates fired in each control. All four ordinary cells hit the
internal 60-second wall cap without a model or verified relation. The outer
safeguard did not fire.

| Degree | Policy | Matched Q1424 forward pair roots | Q1425 forward pair roots | Q1425 reverse calls | Sparse partners kept | `log2` raw mul+sqr+inv calls | Peak RSS |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 53 | `reverse_target` | 58,515 | 21 | 985,233 | 0 | 27.53 | 1,504 MB |
| 53 | `reverse_mid` | 225,790 | 0 | 1,008,552 | 0 | 27.56 | 1,390 MB |
| 83 | `reverse_target` | 65,290 | 1 | 569,521 | 0 | 28.00 | 550 MB |
| 83 | `reverse_mid` | 135,141 | 0 | 562,424 | 0 | 27.98 | 542 MB |

The [work ledger](../work_ledger.json) and per-cell receipts retain each
mul/square/inversion count, conflicts, exploratory wall time, and raw memory
peak. The reverse rule eliminates almost all **complete** pair-root evaluations in
these capped paths. It does so by computing many reverse roots: every tested
ordinary reverse-root candidate exceeded the sparse weight bound, whereas
the known-witness controls retained the correct candidate. The field-call
totals are larger than in the matched Q1424 caps. These are partial costs of
unsuccessful attempts, in raw primitive counts; they are neither calibrated
field-operation equivalents nor completed decomposition costs. There is no
N53-to-N83 solve-growth fit and no degree-131 complete `2^x` estimate.

The [exact pair-support screen](pair_support_screen.json) proves a sharper
conditional statement. For fixed nonzero sparse coordinates `a,b`, the
`S3(a,b,m)` polynomial has at most two roots in `m`; hence a fixed `a`
admits at most `2M` intermediate coordinates with a sparse partner, and
all sparse pairs together admit at most `2M²`, where `M` is the exact
number of nominal nonzero sparse x coordinates. The bounds include
non-lifting coordinates, so they are generous to the solver.

| Degree and weight | Exact nominal `M` | Independent uniform-`m` trials before a sparse partner, at least | Independent uniform-`m` trials before *any* sparse pair, at least |
| --- | ---: | ---: | ---: |
| N53, W≤3 | 24,857 | `2^37.40` | `2^22.80` |
| N83, W≤5 | 30,967,383 | `2^57.12` | `2^32.23` |
| N131, W≤6 | 6,559,349,863 | `2^97.39` | `2^64.78` |

The trial values follow only when each proposed intermediate is independent
and uniform over the full field. Q1425's SAT search uses target-coupled,
adaptive intermediates, so these are **not** its measured solve costs or a
complete degree-131 work estimate. The N131 all-pair figure does show why a
random-intermediate membership strategy cannot be the intended next method:
it exceeds `2^61` logical trials before collection under that sampling law.

The next method gate is a compact, **structured pair-sum membership and
witness method**. It must preserve exact four-point solutions while avoiding
both Q1425's random reverse-root rejection loop and a full quotient-pair
index. The [Q1416 exact-base screen](../runs/n131_q1416_exact_base_pair_index_screen.json)
models a pure full pair index at roughly `2^89.36` logical actions and at
least `2^60.28` bytes for keys alone under its stated uniform-key law;
the model is not a bound on other decomposition methods. That pure-index
family is not a credible below-`2^61` route. First reproduce the
archived representable N53 ordinary target without witness pins; then test
the exact Q1325 N83 base and public target. Only if that stage passes should
a frozen fresh-target panel estimate natural yield and cost per useful row.
