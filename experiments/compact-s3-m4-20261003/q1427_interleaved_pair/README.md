# Q1427: interleaved target-conditioned second pair

Q1426 put the exact factored `S3(leaf2, leaf3, mid1)=0` equations in the
Boolean formula before search, but its Q1425 decision policy completed
`leaf2` before branching on `leaf3`. This stage keeps the exact same CNF,
target list, factor base, external pair-root checks, leaf-lift rule, caps,
and target-first order through the two pair intermediates. It then decides
the second pair's leaf bits in the order
`leaf2[0], leaf3[0], leaf2[1], leaf3[1], ...`. The target and first pair
have already fixed or constrained `mid1`, so the second-pair equations can
propagate while both partner leaves are partial.

This is a decision policy change only: it cannot remove a valid
decomposition. The [frozen protocol](protocol.json) pins the same exact
N53/N83 curve IDs, enumerated-set digests, actual usable base sizes,
folded columns, public targets, target-preimage lists, workload IDs, and
60-second/one-million-conflict caps as Q1426. Freed-partner witnesses are
correctness controls; ordinary cells are unpinned. The control comparison
is Q1426 on the identical formula. Source, binary, CNF, and checked Sage
runtime hashes are pinned before ordinary runs.

The stage is proposal `Q1427`, with `candidate_id: null` and
`isogeny: "none"`. The `PS1...PDP4theory...` ID labels this exact solver
stage, not a complete `IC1` candidate. A single successful ordinary cell
would establish a working point-decomposition path on that target, but not
natural relation yield or a complete degree-131 work projection. Record
timeouts, operation counts, and memory. CPU walls on this host are
exploratory under the repository isolation rule.

## Frozen results

The [four-cell verification](verification.json) reconstructs each CNF and
independently replays both SAT controls. Each control returned one verified
four-point relation. The two ordinary cells remained censored at the
60-second internal wall cap:

| Degree | Cell | Status | Verified relations | Reverse pair-1 calls | Field calls `(mul, square, inverse)` | Peak child RSS, bytes |
| --- | --- | --- | ---: | ---: | --- | ---: |
| 53 | Freed-partner control | SAT | 1 | 1 | `(283, 1,668, 24)` | 25,444,352 |
| 53 | Ordinary | Censored | 0 | 135,226 | `(4,287,739, 24,557,058, 316,213)` | 256,786,432 |
| 83 | Freed-partner control | SAT | 1 | 1 | `(307, 2,598, 24)` | 46,202,880 |
| 83 | Ordinary | Censored | 0 | 71,988 | `(3,527,899, 30,095,340, 288,004)` | 162,594,816 |

The matched Q1426 ordinary cells made 1,080,547 and 485,107 reverse
pair-1 calls at N53 and N83. Interleaving reduced those counts by factors
of 7.99 and 6.74 within the same cap, and reduced the partial raw field
call totals by factors of 7.28 and 6.74. All 270,452 N53 and 143,976 N83
reverse roots still failed the sparse weight rule. Neither stage completed
an ordinary decomposition in its cap. These are algorithmic diagnostics;
raw multiplication, squaring, and inversion counts are not equal-cost
operations, and this host does not meet the CPU isolation gate.

There is no measured natural relation yield or cost per useful row. A
complete degree-131 `2^x` still cannot be projected from these censored
cells. The next solver change must test pair-sum feasibility without
enumerating target-derived reverse roots one fully assigned leaf at a
time, for example by preserving the binary XOR structure during algebraic
elimination. That mechanism needs its own exactness proof and ordinary
query measurements.

## Reproduction

From the repository worktree, before any measured cell:

```sh
python3 experiments/compact-s3-m4-20261003/q1427_interleaved_pair/build_binaries.py --rebuild
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/compact-s3-m4-20261003/q1427_interleaved_pair/sage_runtime_info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1427_interleaved_pair/freeze_protocol.py --check
```

Then run the four cells in protocol `run_order` through
`run_stage.py --degree N --cell CELL` using the checked repository Sage
launcher and verify with `verify_archive.py --require-complete --emit`.
The runner refuses to overwrite existing results.
