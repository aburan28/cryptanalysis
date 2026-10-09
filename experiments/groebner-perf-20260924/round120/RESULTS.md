# Five complete F4 queries are frozen for isolated replay

The host-specific manifest contains five scratch-buffer versus bounded-bitset
pairs with matched query fixtures, proof digests, assignments, reduced bases,
producer work, and checker work. Both optimized/UBSan panels passed 10/10
cases after source commit `c587c950`, and all ten local worker invocations
returned `verified=1`. Each worker emits the target-dependent complete-query
interval and separate matrix, native-F4, and checker phases. The manifest
generator refuses a dirty checkout, stale panel commit, mismatched certificate,
or binary hash drift.

The frozen local manifest SHA-256 is
`7811d76136fe39437933af9d6fd402cc1ea7a354485ae00e62b1d455793a62f8`.
The 10-worker smoke record SHA-256 is
`eca07e5e3ed02dfe3ab3114741264b5461c5e1a1cc349aea9b2cc91fc5a5b434`.
Raw local records are `/private/tmp/f4-isolated-c587-manifest.json` and
`/private/tmp/f4-isolated-c587-smoke.json`; the candidate panels are
`/private/tmp/f4-isolated-scratch-c587` and
`/private/tmp/f4-isolated-bitset-c587`.

The strict preflight on the local macOS host returned `ok=false` with
`requires Linux; this host cannot certify CPU/NUMA isolation`. Its local
receipt is `/private/tmp/f4-isolated-c587-probe.json` with SHA-256
`93255302997247884869789a0ab1fcbe3b73e4fadf8dca99cc2f99080d11e0e4`.
The next execution needs a physical Linux host configured to pass
`scripts/isolated_bench.py probe`, with the binaries rebuilt there. Submit the
host-specific manifest only after that preflight and retain the service's
paired raw rows and host counters before interpreting a CPU wall ratio.
