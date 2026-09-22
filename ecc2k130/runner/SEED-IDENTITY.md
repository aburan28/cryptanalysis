# Shared campaign seed ownership

Cloud workers now acquire a permanent identity and exclusive owner from
`seed-registry/curve-131/` in the shared campaign bucket before starting a
client. A storage prefix does not create a different seed space: run ID
12000 in two prefixes would otherwise walk the same seeds.

`aws/seed_registry.py` is byte-identical to the guard used by the legacy
`aburan28/crypto` fleet and standalone Modal GPU/CPU collectors. It uses
conditional S3 writes, retains historical IDs, refuses a used ID without
its matching full checkpoint, and never expires an active owner automatically.
A missing heartbeat cannot prove that the old GPU stopped. An exception while
the child is still alive retains ownership. Clean shutdown preserves the
maximum checkpoint iteration and releases only that exact owner.

The historical inventory imported 225 run IDs, including 11 distinct active
assignments. Older ambiguous upload directories were decoded in full rather
than inferred from their labels. Existing owners were retained as `legacy:`
owners: they must be confirmed stopped before a replacement is admitted.
If the checkpoint is lost, retire the run ID instead of restarting its seeds.

The cloud preflight checks registry readiness before renting the campaign's
GPU workers. The Docker image and Modal readiness image include the guard.
`ECC_SEED_BASE_IMAGE` can layer the supervisor files over an existing validated
image, preserving the client binary and checkpoint format. The 2026-09-21
deployment used base image `im-LEaik53IOCmWvHm1O2UUPQ`; its live probe confirmed
registry access and rejection of an already-assigned ID. No replacement GPU
campaign was started by the guard deployment.

Recovery is explicit: inspect the exact owner, establish that its process has
stopped, retain the latest compatible checkpoint and corpus, then release
that owner using `SeedRegistry.release(run_id, owner, checkpoint_path)`.
Never delete identity records or reset their checkpoint floor. An old image
or direct binary invocation that bypasses the guard is outside this protocol.

This is prevention of duplicated computation, not a change to the walk or
its mathematical collision-search complexity. Distinct seed ranges can still
produce legitimate meetings between walks.
