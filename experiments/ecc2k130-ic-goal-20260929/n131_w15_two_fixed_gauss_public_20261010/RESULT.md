# Wider native-XOR matrices are admitted but do not clear the N131 search gate

Raising CryptoMiniSat's Gaussian-matrix column limit from its default 1,000 to 4,096 and allowing eight matrices admitted **seven** native-XOR matrices during initialization of the exact two-fixed-seed W15 public formula, compared with **one** under the default policy. The six default-policy “too many columns” events disappeared. Subsequent matrix-initialization passes used zero matrices in both runs: 11 later passes under the default policy and 13 under the expanded policy. This isolates a solver-policy effect, while the public-point solve remained capped.

The [frozen protocol](protocol.json) binds the same published target, source, circuit, one worker, 600-second construction-plus-search cap, and 4-GiB combined-RSS cap as the [default-policy gate](../n131_w15_two_fixed_seeds_public_20261010/RESULT.md). Both producers generated the **same decoded public XCNF**: SHA-256 `449d3e5296b07a8473ff3b99f7dee80af74d5c45469abfe7913a57b3a77e3674`, 117,252 variables, 424,423 CNF clauses, and 42,855 native-XOR rows. The constructed control again passed a full XCNF assignment and exact group lift, with identical decoded control-formula SHA-256. The two compressed files have distinct gzip wrappers; their decoded formula bytes are the comparison boundary.

| Published-point solver policy | Default matrices | Expanded matrices |
| --- | ---: | ---: |
| Initially admitted Gaussian matrices | 1 | **7** |
| Logged too-wide matrices | 6 | **0** |
| Later matrix-initialization passes with zero matrices | 11 | 13 |
| Construction plus search | 592.112 s | 592.103 s |
| Sampled peak combined RSS | 685,441,024 B | 771,653,632 B |
| Terminal status / model lines | `CENSORED_TIME` / 0 | `CENSORED_TIME` / 0 |

The [result](result.json), [compressed formula](system.xcnf.gz), and [raw solver log](solver.stdout.txt) retain the capped attempt. The [terminal audit](terminal_audit.json) checked source hashes, both formulas, trace clauses, solver activity, and resource accounting. A separate [matrix-use audit](matrix_usage_audit.json) compared the exact decoded formulas, target points, logged matrix counts, solver flags, and raw-log hashes. These are unisolated-host stage diagnostics; censored intervals do not determine a wall-time speedup. This proposal retains `candidate_id: null`.

The next method gate moves the target into a multi-block algebraic join before source-mask expansion. The existing N41 unpinned relation supplies an exact full-group control. Use the seed-bucket S3 norm and rotated four-atom product-space inverse to reject joint product families, then require a source-bound one-worker N131 work/RSS projection under 600 seconds and 4 GiB before querying the published point again. Relation yield and novel rank follow an ordinary, independently replayed N131 decomposition.
