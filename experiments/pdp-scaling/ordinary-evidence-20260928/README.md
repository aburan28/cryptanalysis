# Ordinary-query campaign: observed results

Frozen source tree: `fefac7d2d198f57ab23914c1c30c2895be52576e`, published as [0e0d552](https://github.com/aburan28/cryptanalysis/commit/0e0d552bf4380ecdd6e607c667435f144bd60651). The local pre-execution snapshot had identical tree content. Source-file digests are also in every manifest and host receipt.

**Conclusion: no 2× cost-per-new-independent-row improvement is established.** This is a bounded relation-collection diagnostic, not a completed large-base ECC2K83/131 evaluation or a DLP result.

## Measurements

Each backend received the same 60 ordinary n=13 queries (five seeds, 12 each), and the same eight ordinary n=83 queries (two seeds, four each). Rank restarts on each seed: the listed ranks are separate replications, not a global sum of distinct rows across seeds. All 35 backend/seed cells finished; individual polynomial attempts can still time out.

| Field degree | Backend | Verified queries | Independent rank by seed | Charged wall seconds, all seeds |
|---|---|---:|---|---:|
| 13 | direct | 19 | 3, 3, 7, 3, 3 | 1.514 |
| 13 | cryptominisat | 16 | 2, 3, 7, 2, 2 | 52.527 |
| 13 | hybrid-cryptominisat | 16 | 3, 3, 4, 3, 3 | 52.559 |
| 13 | repository-f5b | 0 | 0, 0, 0, 0, 0 | 61.428 |
| 13 | block-f4 | 0 | 0, 0, 0, 0, 0 | 61.423 |
| 83 | direct | 0 | 0, 0 | 32.443 |
| 83 | cryptominisat | 0 | 0, 0 | 49.491 |
| 83 | hybrid-cryptominisat | 0 | 0, 0 | 49.517 |
| 83 | repository-f5b | 0 | 0, 0 | 49.492 |
| 83 | block-f4 | 0 | 0, 0 | 49.463 |

The n=13 original base has 29 geometric points and 26 distinct nonidentity projected subgroup points, giving 13 signed columns. The n=83 original base has 55 geometric points, 52 projected points and 26 signed columns. Each verified row was checked by point arithmetic and separately replayed with finite-field matrix elimination. The modulus has an exact recursively checked primality certificate.

All eight n=83 queries were nondecomposable over the frozen original base according to exact direct enumeration. Every n=83 polynomial attempt timed out inside the combined encoding/solve watchdog. The polynomial workers report unknown rather than UNSAT. No n=83 cost per independent row is finite.

The 2× gate reports **insufficient evidence** for every challenger. The n=13 samples do not reach the predeclared rank-eight minimum per seed, and n=83 has zero rank. The observed n=13 direct collector is cheaper than these tested polynomial paths; this does not compare optimized compiled collectors or other encodings.

## Why the n=83 probe cannot settle the goal

The explicitly enumerated n=83 base has uniform-query coverage at most `53^3/(2417851639230796216685689-1) = 6.157408402748938e-20`. The extra point is the zero image under cofactor projection. This is a counting upper bound, not a fitted success probability. Zero yield here says little about solver quality.

For three summands, even allowing 1% coverage requires on the order of 29 million projected points by this loose ordered-tuple bound; satisfying it would still not guarantee that coverage. The next research step is a feasible larger or implicit base and a compatible encoding, or a separately specified query law/summand count. More trials on this tiny base cannot establish the requested n=83 relation throughput. ECC2K131 remains unrun.

## Accounting and limitations

All arms pay the same measured frozen-base and query-construction costs once, plus fresh-process wall time, equation/index construction, failures, timeouts, group verification and incremental rank. Dependency installation and the separate post-run audit are excluded explicitly. RSS is a process maximum, not simultaneous process-tree memory. Source hashes, exact point sets, scalar seeds and public targets are retained. Solvers never receive the generating scalar.

Runs were serial on the available shared CPU environment, not a reserved benchmarking host. A short local validation run overlapped part of the n=83 probe; timings are therefore bounded feasibility observations, not publication-grade performance estimates. The source-protection limits are one thread, 2 GiB address space, one second per polynomial attempt at n=13, three seconds at n=83.

The tested algorithm set is the direct Python collector, CryptoMiniSat native XOR, three-bit SAT assumptions, repository Boolean F5B, and the block F4 prototype. M5GB, Magma, PolyBoRi, msolve, and Groebner.jl trace reuse were not run in this ordinary-query trial. Cold subprocess and explicit Python descent overheads are included, so these totals do not isolate kernel speed.

## Reproduction and archived receipts

`n13.json` and `n83.json` are the frozen launch manifests. `n13-comparison.json` and `n83-comparison.json` expose every cell and gate result without unpacking. `tests.json` and `tests-*.txt` retain successful local checks: 18 protocol/research/metrics tests passed, three optional integration tests skipped, and five mathematical tests passed.

`n13-raw.tar.xz` and `n83-raw.tar.xz` contain every request, original equation file that completed construction, solver stdout/stderr, incremental journal, per-cell summary and host receipt. Identical files use internal tar hardlinks. Every member was read back and checked against `n13-files.json` / `n83-files.json`; `archives.json` records archive sizes and SHA-256 digests.

```sh
cd experiments/pdp-scaling/ordinary-evidence-20260928
tar -xJf n13-raw.tar.xz
tar -xJf n83-raw.tar.xz
cd ../../..
python experiments/pdp-scaling/ordinary_campaign.py run experiments/pdp-scaling/ordinary-evidence-20260928/n83.json /tmp/new-n83-run
```

The run command rejects changed source hashes. Use the frozen commit or explicitly freeze a new manifest for later code. Preserve the earlier receipts; new runs use new output directories.

`stage-profiles.json` provides derived `EC1` / `PS1` identities, exact stage records, and per-workload run IDs. These labels describe measured stages; all complete-pipeline candidate IDs remain null.
