# ECC2K-130 public gateway activation and device validation

- **Status:** `open`
- **Kind:** access/approval limit, missing abuse controls, and missing live measurement
- **Affected work:** [public contributor network](../ecc2k130/runner/public/README.md), [admission and scale plan](../ecc2k130/runner/public/ADMISSION-AND-SCALE.md), [deployment template](../ecc2k130/runner/public/deploy/aws-gateway.yaml), [PR #874](https://github.com/aburan28/cryptanalysis/pull/874)
- **Next action owner:** gateway engineering and release operator
- **Last updated:** 2026-10-14

## Problem

The ECC2K-130 DP32 contributor gateway cannot yet accept global CUDA workers because its persistent AWS IAM role and public host have not been authorized or created, the container has not run on an NVIDIA device against that host, and untrusted-upload admission, seed auditing and public-path capacity have not been implemented or measured.

The requested system uses the legacy sigma walk for the existing `ecc2k-130` campaign, a single shared S3 seed registry, an invited HTTPS gateway, write-once S3 raw DP batches, and the existing RDS `report_dp` pool. The proposed deployment is in account `590183823895`, region `us-west-2`, with a candidate public run-ID interval of 50000–50999. This is a proposed allocation, not an active reservation. Publishing images or passing host-side known answers alone does not establish a running distributed campaign.

## Evidence and uncertainty

- **Observed:** The [gateway and worker source](../ecc2k130/runner/public/) and [CloudFormation template](../ecc2k130/runner/public/deploy/aws-gateway.yaml) merged through PR #874. Host-side Docker builds, campaign known answers, local gateway tests, Compose configuration, and read-only CloudFormation template validation completed. The [v0.1.0 prerelease](https://github.com/aburan28/cryptanalysis/releases/tag/ecc2k130-public-v0.1.0) publishes source-bound Linux amd64 images; [tagged CI](https://github.com/aburan28/cryptanalysis/actions/runs/38513181174) passed for both. Anonymous manifest reads succeeded for both images, and the worker's config and all 15 layers accepted anonymous HEAD requests. The automatic approval review rejected creation of a persistent IAM role with access to the join/RDS secrets and seed registry, asking for explicit authorization of that exact boundary. The stack was not applied; a full remote image download, public endpoint, and NVIDIA device path were not tested.
- **Derived or proved:** No mathematical conclusion follows from these engineering checks.
- **Suspected explanation:** None needed for the approval refusal. Any later deployment or GPU failure requires its own diagnosis.
- **Missing capability:** Explicit authorization for the reviewed cloud resources, followed by a reachable public host and a device-backed test. The ECC Challenges website's server-side key service and gateway exchange for revocable, run-scoped credentials are not present; the current status site is static. Credential-level quotas, independent DP32 seed replay, quarantine before RDS, durable queued bulk ingestion, worker backpressure and a measured load gate are separately missing. The current ingester sends every structurally valid batch into RDS with an `unverified` label; that label does not stop database pollution. The single host and row-call ingestion path have no public-path throughput measurement.
- **What this evidence does not establish:** Public TLS reachability, image behavior on an NVIDIA GPU, successful live S3 reservation, RDS ingestion, resistance to fabricated DP records, sustained global throughput, or a verified challenge answer.

## What would unblock it

- [ ] Approve the exact merged [deployment template](../ecc2k130/runner/public/deploy/aws-gateway.yaml), including its persistent scoped IAM role, generated join secret, public EC2/EIP, encrypted EBS, S3 writes, RDS secret read, and ongoing charges; record the source commit and selected VPC/subnet.
- [ ] Re-audit run IDs 50000–50999 against current registry and historical owners immediately before deployment; reject the range if any unguarded writer could overlap it.
- [ ] Apply the stack and retain its resource IDs, image/source digests, health and certificate checks, one conditional S3 reservation, one actual NVIDIA device run and upload, and one RDS sample lookup with a durable receipt. Replay any collision independently before a scalar claim.
- [ ] Before widening invitations, implement the [admission and scale plan](../ecc2k130/runner/public/ADMISSION-AND-SCALE.md): site-issued revocable API keys and run-scoped capabilities, quotas, sealed object queue, independent exact DP32 replay with post-commit random sampling, quarantine, a separate public candidate index with bulk collision-preserving ingest, worker pause on backpressure, and isolated load tests at the planned fleet size. Preserve mismatches and timeouts as distinct outcomes.

Authorization is necessary to attempt live rollout; it is not evidence that the deployment works. Successful checks would establish a functioning bounded contributor path, while fleet throughput and any mathematical result would remain separate obligations.

## Next discriminating step

- **Action or proof obligation:** After approval and merge, apply the pinned template to one host and run one invited worker through registration, GPU walk, S3 archive, and RDS ingestion before opening invitations.
- **Inputs and controls:** Use the committed CUDA known-answer file, exact image digests, the existing campaign metadata, a fresh seed audit, local protocol tests, and a separately tracked worker run ID. Preserve raw DP and checkpoint receipts.
- **Execution limits and stop condition:** One host and one GPU worker for the initial device check; stop before inviting more workers if registry, TLS, archive, GPU, or RDS checks fail. Keep the optional RDS ingester confined to this bounded trusted test until the audit and admission gates exist. These are rollout safety limits, not a research campaign budget.
- **Outcomes and next actions:** A valid end-to-end receipt permits a separately monitored fleet ramp; a failed component remains an infrastructure or implementation issue with its raw logs retained; an incomplete check leaves live readiness unverified. A collision triggers independent seed replay and coefficient recovery, not an automatic result claim.
- **Recheck trigger:** Explicit authorization, a new merged source commit, or a changed cloud/registry configuration.

A planned step is not a completed experiment. Apply the existing execution, review, budget, and archival rules before acting on it.

## Resolution and history

- 2026-10-13: Recorded the prepared PR, local checks, and automatic approval rejection of IAM role creation. Unresolved.
- 2026-10-13: PR #874 merged as `c8cc56d8c98705c7f84a21aae1e042453e0105e6`; v0.1.0 images published with passing tagged CI and anonymous registry metadata access. Live activation and device validation remain open.
- 2026-10-14: Added the public abuse and scale obstruction after tracing the gateway, row-call RDS ingester and existing separate bulk ingestion path. The exact security and throughput gates are in the admission and scale plan; no live measurement or cloud change was made.

Completing this record or merging its PR does not establish a research result.
