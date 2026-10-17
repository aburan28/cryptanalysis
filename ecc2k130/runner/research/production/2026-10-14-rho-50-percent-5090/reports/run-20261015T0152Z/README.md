# RTX 5090 paired rho screen, 15 October 2026 UTC

This write-once report covers both RunPod attempts in this session. It reports native client observations only. `build_report.py` reads the two frozen `runs/` directories and regenerates `summary.json` and `rates.svg`; `typst compile report.typ report.pdf` renders the PDF.

## Attempts and custody

| Attempt | Pod | GPU / driver | Outcome | Raw record |
| --- | --- | --- | --- | --- |
| Community Cloud | `3u49fzio9cpsva` | RTX 5090 / 580.173.02 | CUDA device initialization failed in both pinned and candidate binaries; zero timed samples | [`runs/20261015T012515Z/result.json`](../../runs/20261015T012515Z/result.json) |
| Secure Cloud | `ch6h0n2mfz7xo6` | RTX 5090 / 580.126.16 | Six compatibility cases passed; 39 complete warm/timed/return samples | [`runs/20261015T013232Z/result.json`](../../runs/20261015T013232Z/result.json) |

The failed host's raw result has SHA-256 `307a44c3ccee44de7f52381838f9d5ac343041e88be6f5a0a557521ff844bffb`. The completed result has SHA-256 `b598a747a5446d717cdd85063c0423c50b93978684d10fd6de06c980cb478c1c`. Both run directories also contain `build.log`, `run.log`, the tested candidate binary, RunPod create and delete receipts, and host-specific diagnostics. The completed run adds `pinned-smoke.log`. Both delete receipts show HTTP 204 and follow-up HTTP 404. The first failure does not measure mathematical or client throughput; the second host running the pinned binary shows that the CUDA startup failure was host-specific in this test.

The source commit was `fb5ae4b9b9ef5c24780d5a82d04102ecffda2dd5`, with empty source dirty list. The source tar SHA-256 was `a4e1f5542420269af9771fa4e50c5ab6b76336afefc7633ff9fcda7a7cd4fb95`. The driver SHA-256 was `40d20a2ffd7dc6a846b155f14153cdd855b8e176dc366fc9071816cdbc7aaa81`. The pinned live binary SHA-256 was `0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4`; the successful four-warp binary SHA-256 was `7da34f13f191e8317e57cd9e8cd76788c7592954c2ba9ac4f5a707d1400ac294` and matches the locally saved file. The first host's separately compiled candidate had SHA-256 `f5032b783bba304df133a349eda7ab2348d8af42b45b3eb8d3e18492f713a69f`.

## Recorded measurements

Each timed sample completes `workers × 16 × 1,024 × 64` scalar updates, with DP weight 32. Five pairs alternate A/B and B/A order. A and B had identical sorted DP32 records at each population, exact completed update counts, and zero dropped records. Six cross-binary fresh-state and bidirectional-resume cases passed, including 10,249 host-reference verifications. The completed run started at 01:36:14 UTC and ended at 01:49:14 UTC.

| Workers | A rate min / median / max | B rate min / median / max | Paired B/A min / median / max | DP32 records per sample |
| ---: | ---: | ---: | ---: | ---: |
| 87,040 | 13.611 / 13.678 / 13.811 | 14.626 / 14.681 / 14.787 | 1.0707 / 1.0745 / 1.0782 | 254 |
| 108,800 | 12.581 / 12.606 / 12.632 | 15.594 / 15.637 / 15.692 | 1.2395 / 1.2418 / 1.2422 | 321 |
| 120,320 | 13.165 / 13.182 / 13.207 | 10.342 / 10.350 / 10.355 | 0.7838 / 0.7847 / 0.7856 | 355 |

Rates are billions of complete scalar updates per second. All 15 paired ratios, raw sample output and commands, GPU telemetry, corpus hashes, and return-control rates remain in [`summary.json`](summary.json) and the completed raw result. The fastest tested A median was 13.678405 billion/s at 87,040; the fastest tested B median was 15.637188 billion/s at 108,800. Their derived rate ratio is 1.143203 across different worker counts. The 1.5× raw-rate screen against the best tested A median is 20.517608 billion/s; B stayed below it in this screen. No campaign throughput or target-search-time estimate follows from this local client test.

The plot is [`rates.svg`](rates.svg), rendered into [`report.pdf`](report.pdf). The PDF and source describe the first infrastructure failure and the completed paired comparison together. The test excludes S3 upload, ingest, collision handling, long-duration behavior, and recovery accounting.
