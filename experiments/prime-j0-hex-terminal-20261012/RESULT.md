# Voronoi-clipped fixed-base scalar table

The opt-in secp256k1 radix-256 fixed-base evaluator builds **174,883 point entries**:
15 ordinary windows with 10,924 entries each and an 11,023-entry direct
terminal table. The prior direct-terminal format uses 177,174 entries.
The native opt-in evaluator retains 11,505,936 bytes and passed its
65,536-residue atlas audit. It retains the same fifteen digit recodes and
at most sixteen selected points per scalar.

The [source-linked report](REPORT-2026-10-12.md) and
[three-page PDF](REPORT-2026-10-12.pdf) include the pipeline diagram,
quantitative storage graph, exact receipts, open checks, and canonical-graph
review. The paired [macOS](storage-macos.json) and
[Linux container](storage-linux.json) execution manifests record exposed
hardware, affinity, cgroup limits, co-runners, and page-placement availability
alongside the deterministic table-accounting outputs.

The exact construction and proof map are in [PROOF.md](PROOF.md). The
`search.json` census gives 66,133 admissible terminal pairs; `screen.json`
checks 4,096 design scalars and 1,536 scalars from three frozen holdout
panels, including representative geometry and direct row addresses. The
macOS ARM64 native replay checks 2,048 independent secp256k1 points in four
512-case panels against the radix-286 reference. All points match. The
candidate selects 7,679 additions in the first panel and 7,680 in each of
the other three; the reference selects 7,680 in each. The candidate retains
11,505,936 bytes against 14,309,128 for radix-286 and 11,652,560 for the
prior direct-terminal evaluator. These addition counts describe the frozen
panels, not a wall-time speedup.

`native_overlay_hex.py` builds a disposable opt-in binary from the pinned
main-tree native source. `replay.py` checks binary/source hashes, compares
native points against independent fixtures, and keeps raw panel hashes.
The fourth fixture, `holdout.json`, was generated after the candidate source
was frozen and is disjoint from the design set and prior panels. The fixture
records its generator, scalar-stream, and disjointness hashes; `replay.json`
records the executed source hashes.
`replay.json` retains semantic and output hashes; `local-build.json` retains
macOS binary and compiler hashes. The same four-panel semantic receipt passed
in an offline Linux ARM64 container, rebuilt with Rust 1.93.1; its image,
overlay, and binary hashes are in `linux-build.json`. This container runs in
a macOS Docker VM, so it establishes cross-OS correctness and compilation,
not physical Linux CPU performance. Controlled CPU time remains pending a
host that passes the isolated benchmark preflight.
