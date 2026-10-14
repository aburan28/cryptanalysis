# Public DP admission and capacity plan

**Status:** Design and rollout gate, 2026-10-14. The public images exist, but
the proposed AWS endpoint is not deployed. This document does not qualify the
current gateway for open registration or a large contributor fleet.

## Where the endpoint lives

The [current deployment template](deploy/aws-gateway.yaml) proposes one EC2
host in the campaign's `us-west-2` VPC. An Elastic IP and Caddy terminate
public HTTPS at `https://<elastic-ip>.sslip.io`; Caddy forwards to the Python
gateway on a private Docker network. The gateway assigns an S3-reserved run ID,
stores credentials and upload cursors in SQLite on encrypted EBS, and writes
each raw DP batch to a write-once S3 key before acknowledgement. A separate,
optional ingester writes those records into the existing RDS `report_dp` pool.
This address becomes real only after an authorized stack deployment and a
certificate/reachability check. The endpoint must never expose RDS or AWS
credentials to contributors.

The current arrangement is suitable for a bounded invited device test. One
global join token can be copied, the HTTP server and SQLite live on one host,
local staging grows with the backlog, and one ingester sends batches through
256-record `report_many` calls. There is no measured throughput for that
public path. The existing managed S3 ingester's measured rate belongs to a
different, bulk-COPY path; it cannot be assigned to this service.

## Admit untrusted contributors

1. Let the ECC Challenges website issue a separate, revocable API key to each
   signed-in contributor. Its **server-side** key service generates at least
   256 random bits, shows the secret once, stores only a keyed digest plus
   account ID, key ID, scope, creation/revocation times and usage metadata,
   and supports rotation and immediate suspension. Limit how many run IDs a
   key/account may reserve and bind each run to that account. Key creation
   itself needs account and IP abuse limits. A static page cannot safely issue
   or verify keys because it has no private key store. The current published
   ECC2K130 status site is static; its backend or another specified website
   must be supplied before this enrollment flow is real. Keep a separately
   managed emergency stop for enrollment and uploads. Seed IDs are never
   recycled when access is revoked.
2. The contributor's only runtime input should be the image, the HTTPS API
   URL, a persistent `/data` directory, and the site-issued key. Prefer a
   read-only secret file mounted at `/run/secrets/ecc_api_key` over putting the
   value on the `docker run` command line or in an image layer. On first boot
   the container exchanges the site key for one reserved run ID and a short
   lived, run-scoped upload capability. It persists the run identity and
   checkpoint, and refreshes the capability while the site key remains active.
   The gateway may cache key verification briefly, but revocation must have a
   defined maximum delay; a permanent run bearer cannot silently outlive a
   revoked site key. The existing image currently uses a shared join token
   and permanent run bearer, so this is an implementation gate, not a current
   Docker command.
3. Put an edge with connection, request-rate, body-size and timeout controls
   in front of the API. Rate and storage quotas must apply to the credential
   and run ID as well as the source IP. Reject excess work before writing it
   to S3 or reserving another seed range. Keep checkpoints on a separate quota
   from 32-byte DP records. Size those limits from a measured honest GPU rate
   and allow a documented burst for delayed uploads.
4. Require an authenticated manifest for each batch: run ID, byte offset,
   record count, length, SHA-256, walk/version and a server-chosen immutable
   object key. The server grants upload only while the run is admitted and
   within its quota. A presigned S3 URL alone is insufficient: AWS documents
   that reusing its key [overwrites the object](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html).
   Require a signed conditional `If-None-Match: *` write or a bound immutable
   object version, and a signed [S3 checksum](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html).
   The finalizer confirms that object and records one cursor advance.
   Retries of the same bytes at the same offset are idempotent. A changed body
   at an acknowledged offset is rejected.
5. Perform cheap checks before queueing: exact record length and run namespace,
   field width, DP32 weight, and canonical Frobenius-orbit key. These reject
   malformed data, but a malicious sender can generate plausible keys without
   doing the walk. A checkpoint header or checksum proves neither GPU work nor
   the relation between a seed and its DP.
6. Select unpredictable audit indices **after** the complete object is sealed.
   A separate verifier replays the selected seeds from the published challenge
   points, follows the exact sigma walk to its first DP32 point under the
   `2^32` guard, and compares its orbit key byte for byte. Keep the object
   quarantined until its required audit finishes. Audit every new contributor's
   first batch and continue sampling across later batches. Record the object
   digest, chosen indices, verifier source/image identity, limits, outcome and
   resource use. On a mismatch, freeze that run's pending batches, revoke its
   upload credential, preserve raw bytes, and investigate already ingested
   batches from the same owner. An audit timeout is unverified, not a pass.
7. A passed sample changes the batch to *sampled*, not *fully verified*. For a
   random sample of `m` records from a population with forged fraction `f`,
   approximate detection probability is `1 - (1-f)^m`; this assumes the
   sample is unpredictable and the forged fraction is fixed before selection.
   For example, 44 independent samples catch a 10% forged fraction with about
   99% probability. Sparse corruption can evade sampling. Replay **both**
   trails of every collision candidate and independently check any resulting
   scalar relation before treating it as a result. Keep sampled public points
   in a distinct, quota-bound candidate index that can match both the
   existing campaign and other public candidates. Promote an individual
   record to the authoritative corpus only after its own replay. An RDS worker
   label such as `unverified` is metadata, not a validity barrier.

At DP32, [the existing CUDA client](../../src/ec2k_gpu.cu) says a report takes
roughly `2^28` steps, and its host reference replay is slow. The available
`referenceReport` function can check a seed, but the public service has no
bounded, separately provisioned DP32 verifier. Sample rate and verifier GPU
count must be set from a measured exact replay cost. Full verification of
every point may cost work on the order of producing the corpus again. Do not
claim an audit cost or protection level from the present host known-answer
test, which checks different records at a looser weight.

## Keep up with a large fleet

Let `G` be active GPUs, `s` be measured walk steps per GPU-second, and use the
campaign's [internal DP32 estimate](../../README.md) of `2^28.4` steps per
report for planning. The expected
arrival rate is approximately `G*s/2^28.4` records/s and raw payload rate is
32 times that. The illustration below assumes 20 billion steps/s per GPU;
it is a scenario, not a measurement of invited devices or this gateway.

| GPUs | Expected DPs/s | Raw DP payload/day |
| ---: | ---: | ---: |
| 100 | about 5,650 | about 15.6 GB |
| 1,000 | about 56,500 | about 156 GB |

This excludes checkpoints, protocol overhead, duplicates, and rejected data.
The proposed host's 100 GiB EBS volume cannot be the durable backlog at the
1,000-GPU illustration. Move the data plane to immutable, checksum-checked S3
every payload byte. Send finalized object references to a durable queue. [S3
notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html)
may be duplicated or arrive out of order, so consumers must
deduplicate by immutable key/digest and commit their progress transactionally.
Keep the upload/auth metadata store separate from the campaign's collision
table so a flood cannot exhaust the latter merely by registering.

Use independent, bounded worker pools for structural validation, expensive
seed audits, and database ingestion. Parallelize ingestion by object while
retaining global uniqueness within the public candidate index, a lookup
against the existing campaign's key index, and atomic collision recording.
Port or adapt the campaign's bulk-COPY approach only with a same-key,
same-seed duplicate control and a cross-seed collision control: the current
`report_dp` calls implement those semantics, while a separate candidate
index would need them explicitly. The ingester must never consume a pending
or failed-audit object. Raw S3 data remains the replayable source; the queue
and database indexes are derived state.

Expose at least: accepted and rejected records/bytes by reason and owner,
oldest pending object age, queue depth/bytes, sampled/failed/unverified counts,
audit seconds and steps, RDS rows/s and collisions, S3 failures, disk free,
and the time since the last successful drain. Alert on a growing oldest age
even when the HTTP health check is green. Stop new upload grants and return a
retry interval when backlog or storage crosses its measured high-water mark;
the contributor must checkpoint and pause GPU collection rather than letting
its local DP file grow without bound. Existing workers currently retry while
the GPU keeps walking, so that pause behavior is an implementation gate.

## Acceptance gates before a fleet ramp

- Build and independently test exact DP32 replay on a separate verifier,
  including committed known answers, a deliberately altered orbit key, a
  foreign seed, the `2^32` guard, and a verifier timeout. Measure seconds,
  steps, memory and hardware per sampled record. Select the actual audit
  fraction and verifier capacity from those receipts.
- Exercise website-key creation, rotation and revocation, quota exhaustion,
  delayed retries, duplicate
  S3/queue events, changed bytes at one offset, S3 and RDS outages, and a
  forged but structurally well-formed batch. No rejected object may reach
  either collision index; no merely sampled object may enter the authoritative
  campaign table; no acknowledged object may be lost.
- On an isolated bucket and database, load the complete public path for one
  hour at at least 1.5 times the planned peak DP arrival rate, then a 15-minute
  burst at twice the planned peak. Record the generator inputs, object counts,
  API latency, S3 receipts, audit lag, RDS rows/s, queue age, memory, disk and
  cost. After the burst, require a bounded drain and zero unexplained record
  loss or duplicate collision receipts. Do not inject synthetic data into the
  existing challenge campaign.
- Ramp invited contributors in measured steps. At each step, compare accepted
  arrival, audit throughput and RDS drain over the same interval. If any
  downstream rate stays below arrival or oldest pending age rises, hold the
  next step, add capacity or reduce grants, and repeat the test.

The current [activation problem](../../../problems/ecc2k130-public-gateway-activation.md)
tracks the unbuilt admission, replay and capacity gates alongside the cloud
authorization and device test. A design or a green HTTP check is not a fleet
capacity receipt.
