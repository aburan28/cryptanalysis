# Import provenance

Imported from the local `crypto` repository's `ecc2k130/` directory, whose HEAD
was `60587d5730f1742a00ed753ff34b18ecf953b339` at import time (2026-09-20).
Files were copied from its working tree. The source checkout was left unchanged.

The import includes the CPU/CUDA source, generated headers, generators, engine
checks, Modal benchmark/experiment tools, benchmark evidence, and worker/RDS
adapter. Generated binaries, local caches, build outputs, fleet/EC2 provisioning,
and dedicated merge services were excluded. `ENGINE.md` preserves the original
README as explicitly historical notes; `README.md` describes this repository's
cloud runner.

Migration-specific changes are concentrated in:

* `aws/worker.py`: strict S3 → RDS → checkpoint ordering, content-addressed
  deltas, bounded delta copying, unique owners, slot-claim race handling,
  lease renewal during RDS reporting, duration limits and failure exits.
* `aws/rds_gpu.py`: streamed records, aligned offsets, bounded database
  connection/statement timeouts and a lease-progress callback.
* `cloud.py`, `modal_worker.py`, `deploy/`, `build.json`: provider-independent
  launch, campaign/build preflight and a bounded service round trip.
* `tests/`, `Makefile`, documentation and the cloud CI workflow.

The arithmetic source and generated field headers were not modified as part of
this migration. The existing `fpga/` core and Go `orchestrator/` remain separate;
this runner retains its original record/checkpoint protocol.

## Production promotion, 2026-09-21

The accepted `warps4_poly_compact640` build was subsequently promoted from
`research/candidates/goal22/` into `Makefile`, `src/`, `include/`, `generated/`,
and `codegen/`. Its immutable measurement and acceptance receipts remain there.
It uses CUDA 13.3.1, sm_120, batch 16, 640 threads/block, and min-blocks 1.
The measured median is 22.100934 billion updates/sec; DP34 collection measured
21.548499 billion/sec with zero dropped records and a matching reference corpus.
This promotion is separate from the original unchanged-source import above.

Matching legacy benchmark wrappers (`modal_app.py`, `packed_audit.py`) were
recovered from the existing benchmark container so their build-identity and
audit tests match the promoted generators. They are not the production launcher.
That table-profile rollout used `modal_worker.py` and `cloud.py`, an isolated S3 prefix and RDS
campaign, run IDs starting at 10000, and pipelined direct RDS reports. Existing
campaigns and legacy Modal Volume checkpoints are not converted or overwritten.

## Compatible Frobenius deployment and repository placement

The subsequent DP reconciliation selected the legacy-compatible Frobenius walk
at DP32, batch 16, 640 threads/block and 120,320 workers per GPU. The four-GPU
deployment uses run IDs 12000–12003, checkpoint v2 and the existing `ecc2k-130`
RDS collision pool, with checkpoints under `campaigns/ecc2k130-frobenius32-120k-v1`.
The exact deployed binary's replay, resume, corpus and live persistence checks
are recorded in `research/production/2026-09-21-120k-deployment.json` and its
linked receipts.

This PR places the self-contained runner in `ecc2k130/runner/` because the
current default branch already contains the standalone CUDA/CPU/Metal clients
in `ecc2k130/`. The runner's measured arithmetic, generators and build settings
are unchanged by that placement. Documentation and CI commands use the nested
path; container paths remain `/opt/ecc2k130` and `/workspace/ecc2k130`.
Independent pair-table publication tooling and large local research datasets
are excluded. Historical receipts retain the original paths and measurements.
The scoped `.clang-format` preserves the imported C/CUDA files and generated
headers byte for byte; formatting them would invalidate both generator checks
and the source hashes recorded with the measured binaries.
