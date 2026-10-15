# Batch inversion crossover for radix-14 scalar multiplication

The XYZZ evaluator can group a frozen sequence of 128 independent scalar multiplications into chunks, sharing one field inversion within each chunk. `native_batch_size_overlay.py` applies the size selector only to the checked front source from the parent experiment. It accepts divisors of 128 from 1 through 128 and preserves the original 128-output command. The inherited `radix_136531_batch_inverse` native test passed on the RunPod x86-64 build, covering the 128 independent holdout scalars and the identity case. The native front source is SHA-256 `4df1be9f9046774f1f8720e1ba8e4c379df559c7171b636221fa9f572ac03cc8`; the release binary is `c12828226c997b608cc2b6d407e9eaaedff9c38e89a94b24d5f0713d01a6645e`.

## Direct sizing screen

The direct screen used 96 passes over the same 128 frozen scalars for every chunk size, with all 12,288 outputs verified. These timings selected the paired gate and are exploratory because the screen did not use the serial runner's A/A and noise checks.

| Outputs per inversion | Inversions per 128-output pass | Online ms per 12,288 outputs |
| ---: | ---: | ---: |
| 1 | 128 | 141.963422 |
| 2 | 64 | 97.670978 |
| 4 | 32 | 78.819290 |
| 8 | 16 | 68.423161 |
| 16 | 8 | 64.508009 |
| 32 | 4 | 62.930290 |
| 64 | 2 | 61.925214 |
| 128 | 1 | 61.657853 |

Each row returned `verified=1`, `count=12288`, the same fixture hash and final point, and 26,035,988 retained table bytes. The screen's stdout and stderr are frozen in the serial job artifacts.

## Frozen Tier 1 gate

The two manifests freeze size 1 and size 2 against the same individual-inversion reference used in the parent panel. Each has 16 repetitions of A/A, comparison, A/A, with alternating reference/candidate arm order. Every arm computes the same 12,288 outputs, and output replay occurs after the online interval. The accepted comparison needs all arms valid, both adjacent A/A ratios in `[0.90,1.11]`, and a paired bootstrap 95% interval wholly on one side of one. The job runner records the exposed CPU topology, pinning, cgroup pressure and throttling, steal time, frequency, memory, source and binary hashes, and per-arm outputs. The container reports Tier 1 instance conditions; physical-host exclusivity is unverified.

The parent Lean proof `BatchInverse.prefix_reverse_identity` covers an arbitrary finite prefix, so varying the chunk length adds no new mathematical assumption. The chunked command's native holdout and 12,288-output replay provide implementation checks for each selected size.

The panel jobs are `44ccef44e8284befa166b3106b1542c2` (size 1) and `6efe4e5453914fcf9c25ca78ae0d1f04` (size 2), queued in that order on the serial RunPod service. `analyze_crossover_tier1.py` audits the complete raw panels and the exact candidate binary/source hashes after they complete.

## Paired result

The local `analyze_crossover_tier1.py` audit checked the exact frozen manifests, all 192 arm outputs, both 48-pair ledgers, all per-arm binary hashes, the candidate front and arithmetic source hashes, and the sealed artifact status. Every arm was valid and every output matched the same point. There were no A/A failures. The observed cgroup throttling and execution-CPU steal counters summed to zero across both panels.

| Outputs per inversion | Reference mean online ms | Candidate mean online ms | Median paired reference/candidate ratio | Paired bootstrap 95% interval | Result |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 135.4193 | 136.1368 | 0.992657 | [0.991476, 0.994458] | Qualified 0.74% throughput regression |
| 2 | 135.6817 | 98.1519 | 1.379409 | [1.375878, 1.387388] | Qualified 37.94% throughput gain |

Thus **two outputs per inversion is the smallest tested batch size with a qualified throughput gain** for this frozen fixture and Tier 1 envelope. Size 1 uses 128 inversions per 128-output pass; size 2 uses 64. Both retain 26,035,988 table bytes. These are sustained 12,288-output intervals; the size-1 arm makes independent single-output calls, but this panel does not measure isolated one-call latency.

Raw receipts are in `crossover-panels.tar.gz` (SHA-256 `283953447abe4fb18cc78942b967a35815d8b793ee80857da1ee2d0ef31dc695`) and unpacked under the two job IDs. The machine-readable audit is `tier1-crossover-analysis.json`. Reproduce it with:

```sh
python3 experiments/prime-j0-batch-inversion-crossover-20261015/analyze_crossover_tier1.py
```

The results apply to the specified x86-64 RunPod instance, frozen 128-scalar fixture, pinned CPU 13, and listed cgroup observations. A container cannot certify physical-host exclusivity, so this is Tier 1 instance evidence. The direct eight-size screen suggests diminishing gains after size 32, but only sizes 1 and 2 passed the frozen paired gate here.
