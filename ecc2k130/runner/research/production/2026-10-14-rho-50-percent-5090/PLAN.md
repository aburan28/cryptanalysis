# Isolated RTX 5090 Frobenius geometry test

Frozen before pod allocation on 14 October 2026 (America/Los_Angeles). The user authorized an RTX 5090 RunPod comparison following the bounded RTX PRO 6000 screen. The test is local GPU/DP collection; it does not join or modify the campaign.

## Inputs and arms

- One disposable RunPod NVIDIA GeForce RTX 5090 with a CUDA 13 capable driver. The observed provider quote before launch was $0.69/GPU-hour on Community Cloud; the exact pod quote, host and billed duration go in the run receipt.
- A: the exact campaign binary at `s3://ecc2k130-590183823895/bin/f3ab725a533b777e/ecc2k130`, SHA-256 `0c02a3cfec9553a5def6e9df530c027a246648f6a6b8b7fef39c67e582aae9f4`. Download locally and transfer that binary, not AWS credentials, to the pod.
- B: compile the current unchanged `ecc2k130/runner/{Makefile,src,include,generated,codegen}` source with CUDA 13.3.1 using `make gpu-frobenius32-120k`; retain build log, source archive hash, compiler version and B binary hash. This is the same four-warp Frobenius profile screened on Modal, though the new compiler environment may produce different binary bytes.
- Curve 131, signed-Frobenius walk, DP32, batch 16, run ID 11000. Populations 87,040, 108,800 and 120,320; 1,024 steps per launch; 64 launches per timed sample; five alternating A/B pairs at each population. Warm both arms first and end each population with A return control. No post-hoc population selection within a paired comparison.

## Correctness and measurement

Before timing, run the existing host-reference and cross-binary fresh-state/DP-report/checkpoint-resume comparison at populations 640, 641 and 256 and DP weights 0 and 50. Each timed sample must exit zero, complete exactly `population * 16 * 1024 * 64` scalar updates, report zero drops and produce a complete DP32 file. Within each population, sorted DP32 corpus hashes must be identical across A/B samples and the A return.

Report each raw rate and paired B/A ratio, with median and range. The predeclared same-population collection-rate target is 1.50. Compare the fastest tested geometry in each arm descriptively, with the different seed populations called out. If the target is met locally, sustained accepted-DP collection and collision-quality/campaign-cost evidence are still needed before a target-time claim.

## Bounds and records

One pod, one GPU, no create retry after an ambiguous response. A confirmed unavailable offer may be reported without another allocation. 40-minute process timeout after the image is ready; terminate the disposable pod after copying receipts, or on failure. Target total pod lifetime under 90 minutes. The run keeps the exact source and driver hashes, commands, environment, GPU identity, `nvcc` output, build output, full benchmark stdout/stderr, raw JSON, local transfer hashes, provider creation/status/deletion receipts and a derived report with chart and inspected PDF. No production pod, campaign S3 object, slot, checkpoint, database or credential is changed.
