# Pinned native primitives

The files under `src/cryptanalysis/` are unchanged copies from
aburan28/crypto at cdf13a965874ea45720649388f30b8b5291a7176, maintained by the
same repository owner. No separate upstream license file is supplied at that
revision. `UPSTREAM-SHA256SUMS` records their original paths
and hashes. Keep these files byte-identical when updating the snapshot;
namespace bridges in `lib.rs` supply the backend's existing one-word field
and point types, and the existing native SHA-256 implementation.

This small snapshot lets both repositories compile the same wide signed-
Frobenius reference and native ecbench isolation/host primitives without a
network Git dependency or copying the entire ecbench registry into the suite.
It is **not** a sealed ecbench session, registry extension or audit receipt.
The campaign method has a separate identity, checkpoint schema and protocol.
All upstream unit tests remain enabled.
