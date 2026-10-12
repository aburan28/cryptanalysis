# Canonical Solinas XYZZ on the U14 sector schedule

Format 169 evaluates the 14-window Eisenstein sector schedule with one XYZZ
accumulator whose field coordinates are canonical secp256k1 residues. Its
general field multiplies and squares use direct pseudo-Mersenne reduction;
format 168 uses Montgomery field products with the same window choices,
point count, and grouped unit order. The final release replay matched all
4,096 scalar records, and the first 128 points matched independent binary
multiplication.

The panel uses secp256k1, `y² = x³ + 7` over
`p = 2^256 - 2^32 - 977`, with generator
`G = (79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798,
483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8)`
and prime subgroup order
`r = fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141`.
The frozen panel was generated with Python `random.Random(20261010130)` and
successive 256-bit `getrandbits` values, rejecting any residue modulo `r`
already present in eleven earlier panels or in this panel. Its 4,096 accepted
scalars have digest `24708c93cba06a9c0deb0d51d2befd9144f6ed845c6fd1162b9cb6147afe287d`.

| Evidence | Result |
| --- | --- |
| General field arithmetic | 25 boundary operand pairs and 10,000 deterministic pairs matched independent big-integer multiplication; squaring of each first operand matched independently |
| Full scalar panel | 4,096/4,096 format-168 and format-169 point and metadata records matched |
| Independent points | First 128/128 panel points matched binary multiplication |
| Final release CLI | 129/129 fixture rows matched scalar, base point, expected point, mode, and `verified=1` |
| Mathematical reduction | Lean theorem `PrimeJ0Solinas.canonical_product_reduction` proves four folds and one subtraction equal `ab mod p` for `a,b < p`; `canonical_product_result_lt_prime` proves the result is below `p` |
| Proof audit | Lean 4.34.1 built every declaration; `#print axioms` reports only `propext` and `Quot.sound` for the final theorems |
| Implementation host | Darwin arm64; Rust 1.93.1 (Homebrew); release profile |

The [model receipt](model.json) re-sums the frozen 4,096-row paired schedule:
53,248 ordinary mixed additions and 8,167 unit rotations. The source-formula
boundary charges 36 limb products to each Montgomery multiply/square and 23
to each direct Solinas product. It gives **19,357,121** modeled products for
format 168 and **12,434,881** for format 169, a **35.761% reduction in this
operation count**. The model excludes scalar recoding, table construction,
final inversion and conversion, carry instructions, exceptional paths, and
cache effects. CPU wall-time ratio and full-operation speedup remain pending
a paired run with a passing [host-isolation receipt](../../docs/ISOLATED_BENCHMARKS.md).

Each standalone format-169 process prewarms its own 1,004,908 affine points
in canonical encoding. The point table occupies 64,314,112 bytes; the
`retained_bytes` field adds the 96-byte canonical cube-root array and reports
**64,314,208 bytes**. Its initializer also caches a shared 96-byte
Montgomery cube-root array. Counting both arrays gives **64,314,304 bytes**
for these components, still under the 67,108,864-byte table cap. Other shared
field constants, allocator overhead, and construction peak memory are outside
that table accounting. The unit-test process holds both comparison tables;
the standalone CLI process does not prewarm format 168's table.

The [written proof and proof map](PROOF.md) give the four carry bounds and
the exact Lean declarations. The Lean proof establishes the natural-number
reduction algorithm. The 64-bit Rust limb implementation is checked against
independent modular arithmetic and point multiplication; its correspondence
to the Lean function is not mechanically linked.

## Frozen identities

All digests are SHA-256. The release binary and CLI fixture were rebuilt
after the final Rust source change.

| Artifact | Digest |
| --- | --- |
| `src/bin/eisenstein_fixed.rs` | `8e12023271c772b4b8f2b72bd844377fca1e09e059cdb26b5bd03b5e8c76d01d` |
| `src/bin/eisenstein_fixed/unit_orbit_windows.rs` | `a7dc22978968d3716b2015352fabbdfa690a25dafa1914823a259faa3a808d70` |
| Final release CLI binary | `a40c4bd8381115bd0fc59cc878d6ba85f073bac53b7c266403ff9845ec6d180f` |
| 4,096-scalar panel | `1dd3d17f3485c144f045cf0a81394b8d129095b74ac2de9a06e06d6f4ef2cd99` |
| 129-case CLI fixture | `2895d9c40912b090f0e6ce85ef8bb4d92822a83a5626fb376fcb552a556981fb` |
| CLI output | `2b29ca08a65c4fce4676af1a74de40354a3161982ddfed6af5dffed8805a1d96` |
| `model.py` | `24e0f8588f0a168f75b5b7626f503b74f17674ff0062045e2225da452dfe0322` |
| `model.json` | `1ac16ca23057ffea3bf34af30c2b641a6092cd7ae0e2c4d2ff678e319b3c108a` |
| `verify_cli.py` | `3fbb56e078793a0b2bab3878592a6c86c7b11eac89f6115e2ab402de1f624df2` |
| `SolinasReduction.lean` | `6031ae6a3355cfb58801caabeab8e591a1b8870a3072faa20d2a20d79b3afa1e` |
| `lean-toolchain` | `d5edba4e4b8faad9c1baeadb265716d20d03be4d1a2647dc5e35b0c0325bea7b` |
| Lean build and axiom audit | `f2f90351ae88941708279e3565e02add61c9c354cab09a64c1e3aa76878631ba` |
| Field-product test log | `3273635f634dcf78dc72e53d13d505cc7e3f34918ac680dd842f05c5e0aa250b` |
| Full-panel test log | `3a85ff5465debc821385b7c5c784cbe9ef5bda64411a428d65feac59427719bb` |
| Release build log | `0cb21ffecad987e7687f331acf3de0abaf1f8af178e3b9416a15dace04b7e178` |
| CLI verifier log | `815a4d167732a2538647e5c73b56730e938905470b960d676da2d97aa71bd3a4` |

The next run pairs formats 168 and 169 on the same frozen scalar inputs in
the isolated benchmark service. It must include full scalar recoding,
table access, point evaluation, and final conversion in each online interval,
with the common table-preparation boundary recorded separately.
