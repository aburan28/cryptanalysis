# Unit-orbit memory frontier: verified native formats

U15 cuts retained table payload by **55.96%** and U16 by **79.01%**
relative to U14, while adding approximately one and two mixed point
additions per scalar, respectively, on the frozen 6,748-scalar corpus.
All three native modes returned the same verified points.

| Format | Windows | Retained payload | Reduction from U14 | Mixed additions, 6,748 cases | Additions per case |
| --- | ---: | ---: | ---: | ---: | ---: |
| U14 | 14 | 78,470,184 bytes (74.835 MiB) | reference | 87,438 | 12.9576 |
| U15 | 15 | 34,561,176 bytes (32.960 MiB) | 55.96% | 94,164 | 13.9544 |
| U16 | 16 | 16,473,352 bytes (15.710 MiB) | 79.01% | 100,888 | 14.9508 |

The [protocol](UNIT_ORBIT_MEMORY_FRONTIER_PROTOCOL.md) was committed in
`752c950b` before this replay. Its width schedules all cover 129 bits;
the digit norm bound proves exact integer recoding. Each format retains
one affine point per six-unit residue orbit per position, including
identity placeholders. Payload counts include point slots, both
residue maps, canonical digits, table pointers, and struct metadata;
allocator rounding and page mapping are separate.

The [native receipt](unit-orbit-memory-frontier-verify.json) records
source and binary hashes, the scalar-input hash, output digest, memory
counts, and addition histograms. It covers the 6,492-case prior corpus
plus 256 fresh scalars from `random.Random(20261009515)` with input SHA-256
`65ab9d09662ccf4dfccfe33726c3b8a5d597bfde71ba767ffaa6300c90def367`.
Every output matched the frozen graph-aware baseline; the fresh 256
points also matched independent multiplication, and all 129 fixture
points matched their expected coordinates. The release Rust tests
passed exhaustive residue-map checks for radices 256, 512, and 1024,
boundary reconstruction for all schedules, and independent group-sum
checks of all 1,671,228 retained slots across the three formats.

These counts define a memory/addition Pareto frontier for the current
point representation. They do not measure online CPU time or cache
behavior. The next experiment is a paired U14/U15/U16 online panel on a
host that passes the [isolated benchmark preflight](../../docs/ISOLATED_BENCHMARKS.md),
including decomposition, lookup, unit action, table access, point work,
and recovery verification within its declared timing boundary. Keep
U15 and U16 opt-in until that result is available.
