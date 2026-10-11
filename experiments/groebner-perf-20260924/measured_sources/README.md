# Exact historical source versions

The summation-polynomial loader gained atomic cache writes in PR #117 after
rounds 4 and 10–13 were measured. Their recorded source hashes still identify
the previous loader. This directory retains those exact bytes under their
SHA-256 digest; it also retains the measured round13 auditor before this
compatibility update. `receipt.json` identifies their original tracked paths
and commit.

Historical audits may read these bytes when the live file no longer matches a
recorded measurement. They verify the full digest and fail on unknown or corrupt
versions. They never install or execute the archived files. No timing records,
successful outcomes, failed attempts, workload identities or binary hashes are
rewritten. Current implementations are built and tested separately in CI.

The live audit inventories are updated for the changed auditors; the measured
auditor source versions remain available in the existing round-specific
snapshots or here. An inventory is an integrity record, not an attestation by
an external party.
