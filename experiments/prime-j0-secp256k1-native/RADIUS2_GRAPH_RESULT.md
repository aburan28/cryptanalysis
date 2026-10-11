# Radius-two matching atlas for fixed-generator tau multiplication

Adding ten distance-two row-pair tables and a 4,096-mask optimal matching
atlas saved **6,298 mixed additions** over the eleven-edge path on a
4,096-scalar holdout. The complete point-operation proxy fell from
**1,061,147 to 991,869 field-product units (6.53%)**. The same selected
Eisenstein representatives, tau counts, and secp256k1 output points
were retained. The 21 edge tables occupy **85,975,344 bytes** of compact
slots, compared with 45,034,704 bytes for the path. These are operation
and storage results; online CPU timing still requires an isolated host.

## Construction and matching

The graph has edges `(i,j)` for ordinary rows `0 <= i < j < 12` with
`j-i <= 2`. Each edge table stores 39,366 points using the existing
sixfold common-unit quotient and 104-byte compact slot. A deterministic
subset recurrence constructs a maximum matching for each of the 4,096
possible active-row masks. The resulting atlas occupies **28,672 bytes**
on this build. For every scalar and comb column, the evaluator forms
the active-row mask, looks up its matching, adds the corresponding pair
points, then adds unmatched row points. The sparse top row keeps its
existing exact repair. This is a variable-time public-scalar method.

The [frozen protocol](RADIUS2_GRAPH_PROTOCOL.md) fixed the two fresh
panels, 90 MiB slot cap, 3% holdout gate, and correctness checks before
screening. The holdout passed that gate.

| Graph | Edges | Retained slots | Holdout fusions | Holdout point proxy |
| --- | ---: | ---: | ---: | ---: |
| Distance one path | 11 | 45,034,704 bytes | 20,944 | 1,061,147 |
| **Distance at most two** | **21** | **85,975,344 bytes** | **27,242** | **991,869** |
| Distance at most three, screen only | 30 | 122,821,920 bytes | 30,298 | 958,253 |
| Complete graph, screen bound | 66 | 270,208,224 bytes | 37,023 | 884,278 |

The design panel of 4,096 scalars had 20,994 path fusions and 27,204
radius-two fusions. The [screen receipt](radius2-graph-screen-result.json)
retains the mask distributions, per-scalar deltas, graph edges, table
sizes, and atlas digests. Every reconstructed path fusion count equaled
the frozen native path report.

The native evaluator passed **50 release tests**, including sampled
direct point-sum checks for all ten new edges and atlas disjointness
checks for every mask. The [differential replay](radius2_graph_verify.py)
passed on **8,540 scalars**: five boundaries, 214 frozen cases, all 129
benchmark fixtures, and both 4,096-case panels. Every affine output,
selected representative, tau count, terminal-repair status, and
independently predicted fusion count matched. Independent Python
secp256k1 multiplication checked 261 boundary and fresh points; all
129 fixture points matched their expected coordinates. The
[verification receipt](radius2-graph-verify-result.json) records panel
totals and exact artifact hashes.

An explicit setup command reported 826,686 pair-table points,
85,975,344 retained slot bytes, 28,672 atlas bytes, and 229,752,832
bytes of peak child resident memory on this macOS ARM64 host. The local
preparation interval was 60,410.380 ms under host contention. It is
reusable fixed-generator setup, outside the scalar online timer, and
is reported only as a resource observation.

| Artifact | SHA-256 |
| --- | --- |
| Frozen screen | `8f087b5454f2eb9770fb4face3ec28fd7a8094b9319f8c21b4536a07d7984829` |
| Native replay | `7ea9b6cd0f0da495c4593d9a21481f591066623c10ca96bfc1afa6decc67b7a5` |
| Candidate source | `bc3935081de6b8247fb0ac8171425f83ac8739a3d775d0e1f131d672180bc239` |
| Candidate release binary | `b9c194c9105ef41daf95cef229d72434d5421e72ffd714dc32ed8ee7bb41f6ad` |
| Path reference binary | `e8ffd24be7ea2c976b9ab8f31cea7d7d1cda0b6fbeb35b7e5b95ba2e1ae411aa` |

The next empirical check is a matched 129-fixture, seven-repeat online
comparison on a host satisfying
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
That run must include matching lookup and compact point decoding inside
the online boundary and preserve every failure. A literature review of
graph-constrained pair precomputation is needed before an academic
priority claim.
