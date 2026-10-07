# Q1484: exact N131 cyclic-window base

The [pre-registered design](design_protocol.json) extends Q1481's exact
Frobenius window-orbit base to the ECC2K-130 field degree 131. The same
long-zero-gap representative rule gives exactly `2^26` raw `x` orbits for
window dimension 27. Rationality, cofactor projection, duplicates, actual
usable points `B`, and folded columns `K` require exhaustive measurement.

The complete point set will be archived as a two-bit status per raw orbit in
the deterministic Q1481 representative order, together with the frozen
projection code and the SHA-256 digest of sorted unique projected orbit keys.
This compact encoding reconstructs every subgroup-usable point by applying
the declared [4] projection and expanding both signs and all Frobenius
powers. It avoids putting a several-hundred-megabyte raw key list in Git.

This is a factor-base geometry experiment. It retains the exact curve ID
`EC1N131Ckb1h6816f880945e`, `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. A nominal dimension is not an `fb<B>` count. No N131
decomposition or complete `2^x` is claimed by this work.
