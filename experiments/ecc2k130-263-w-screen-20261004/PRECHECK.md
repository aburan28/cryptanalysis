# Route-manifest pin correction before the first sample

The first checked-Sage launch (`evidence/run-r1`) stopped at `digest(ROUTE) ==
config["route_manifest_sha256"]` before constructing a curve, basis, mask, or
outcome. Its empty stdout, stderr and `failure.json` are retained. The initial
pin `f9975148e86349840f0efcf42b602d0cb5676a2e06344a16ca2c3096c47e96f4`
came from a stale local file outside this clean worktree. The actual merged
`origin/main` route manifest is
`4b8ce3b607f9fd34c64a157cc904a00b8350e48570d1eaac7b4ca0646f296075`.
The six-line difference only adds the exceptional-input replay and checked
runtime hashes to the `evidence` section and updates the manifest source
hash; field, source/target models, subgroup and map are identical.

The corrected protocol/configuration are committed and pushed before a new
output path (`run-r2`) is launched with the same frozen mask domain, sample
sizes, decision gate and source code. No result was inspected or discarded.
