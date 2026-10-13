# N83 packed-root capacity screen: frozen protocol

The 16-byte packed root table makes K1271 the largest nested base whose
source-level state bound requests at most `2²⁹` slots. The frozen fifth-public-
point screen compares K900, K1271, and K1200 under one 12 GiB sampled RSS
cap. K1200 is a predeclared intermediate and retains a completed comparison
if K1271 is resource-censored. Each candidate will receive the same public
target, rank seed, packed-table flag, and process limits; the tuned rho
reference runs before and after. Every disposition and raw output is retained.

The [protocol](protocol.json) fixes the exact source commit, source hashes,
public target, arm order, resource cap, and online timing boundary. The
[target](target.jsonl) contains only the public point; its known-scalar fixture
is held in a separate [validation sidecar](validation_sidecar.json). The
`run.py` launcher requires a clean pinned source checkout, builds the two
executables with locked offline Cargo, and monitors process RSS. This is a
CPU-only secondary control on a shared Mac; wall ratios will be exploratory.

For the numeric capacity step, the Rust loop visits at most `83*K²` pair
states and requests four slots per state before power-of-two rounding.
[`CapacityBound.lean`](CapacityBound.lean) proves that K1271's maximum request
fits `2²⁹` slots, K1272's maximum request crosses that threshold, and
`2²⁹` slots at 16 bytes occupy 8 GiB. These theorems are conditional on the
source-level state bound; they do not formalize the Rust loop or assert every
state exists. The [proof receipt](proof_check.json) records the Lean 4 v4.34.1
build and axiom audits. The experiment result will record actual state yield,
resource disposition, base cardinality, phase costs, and independent replay.
