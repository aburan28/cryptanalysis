# ECC2K83 explicit factor-base frontier

Frozen source tree and protocol: [PR #163](https://github.com/aburan28/cryptanalysis/pull/163). First run used `manifest.json`. The second frozen case uses `manifest-l17.json` and the separately versioned [amendment](EXPLICIT_BASE_FRONTIER_AMENDMENT.md).

| n | l | Actual projected B | Sign columns | Base preparation (s) | Ordered m=5 upper | Unordered m=5 upper |
|---:|---:|---:|---:|---:|---:|---:|
| 13 | 5 | 26 | 13 | 0.016 | 1 | 1 |
| 83 | 6 | 52 | 26 | 5.503 | 1.72962e-16 | 1.73175e-18 |
| 83 | 12 | 4,054 | 2,027 | 10.673 | 4.53445e-07 | 3.78804e-09 |
| 83 | 16 | 64,904 | 32,452 | 20.155 | 0.476388 | 0.00397051 |
| 83 | 17 | 130,604 | 65,302 | 23.140 | 1 (capped) | 0.130985 |

All original points and projections are preserved in `run-1/n*-l*.jsonl.xz`. See `run-1/results.json` for original/projected counts, exact subgroup-order certificates, point-set digests, sampled checks and ordered bounds. The compressed receipt SHA-256 and byte counts are in `run-1/archives.json`. `run-1/host.json` binds compiler and binary hashes. The enumerator checks every constructed and projected point lies on the curve; Python independently replays all control abscissae and sampled large-base abscissae, including subgroup multiplication.

The preregistered l=17 follow-up is in `run-2/`: 130,604 signed subgroup points and a 13.0985% unordered five-summand ceiling, clearing the *necessary* 1% screen. Its 65,302 sign columns already imply a substantial later rank calculation. This ceiling is not a measured relation probability. There are no observed ordinary relations, independent rows, five-summand solver measurements, or full-DLP speedup in either receipt. In particular, base construction alone cannot establish the requested 2× reduction in time per new independent relation.

The first l=16 raw scratch file was found truncated after the complete run had recorded its hash. A deterministic rerun of the unchanged compiled enumerator produced the exact recorded 3,778,045 bytes and SHA-256. The archive was repaired before publication. Every published compressed file now matches both its archive digest and the original raw result digest; `verify_frontier_archives.py` checks these links and the final summaries. The l=17 archive passed the same check.

Construction and independent audit are charged in `base_preparation_seconds` (compiler and archival compression separately excluded). No factor-base points were substituted from another representation. The earlier Python n=83 l=6 base reproduces exactly; the small n=13 control reproduces exactly. Time is a shared-host observation, with source and work limits retained.

```sh
python -m unittest discover -s experiments/pdp-scaling -p test_explicit_base_frontier.py -v
python experiments/pdp-scaling/explicit_base_frontier.py run experiments/pdp-scaling/explicit-base-frontier-20260928/manifest-l17.json /tmp/new-l17-run
python experiments/pdp-scaling/verify_frontier_archives.py experiments/pdp-scaling/explicit-base-frontier-20260928/run-1 experiments/pdp-scaling/explicit-base-frontier-20260928/run-2
```
