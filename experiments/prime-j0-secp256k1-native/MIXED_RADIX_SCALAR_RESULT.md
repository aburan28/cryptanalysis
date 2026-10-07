# Conditional radix-two exits: fresh secp256k1 scalar panel

The recoder, fixture generator, Sage point validator, and protocol were
frozen in `1aaa8832` and published in draft PR #469 **before** the new
256-case Sage fixture was generated. The original 64-case panel was
design data. The prior selective and portfolio holdouts had already
been inspected and were not reused as fresh evidence. The checked
repository Sage launcher reported `status: verified` in
`mixed-radix-runtime-info.json` (SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).

The new workload has eight bases and 32 scalars per base. All 256
base/scalar pairs are unique and have zero scalar overlap with the
original, selective, portfolio, and linked fresh fixtures. Its input
digest is
`a5f2ecf6371addad3a39dedec4f3bafa39b24810f40a3a44484886efd78b619d`;
`mixed-radix-fixture.json` has SHA-256
`95b5c9040c1a904740116d7990539e8b534ec1d3df495c74aa628c50009726b1`.

| Panel | Cases | Current selective `M+S` | Greedy 2/τ `M+S` | Per-scalar choice `M+S` | Saving vs selective |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original design | 64 | 87,298 | 87,437 | 86,711 | 587 (0.672%) |
| **New Sage holdout** | **256** | **348,864** | **350,135** | **346,955** | **1,909 (0.547%)** |

The selector chose the radix-two stream for 30 design and **108 fresh**
cases; the other 148 fresh cases retained the incumbent.
The new greedy path had no detected cycles or length-limit failures.
The mean selected source-count saving on the fresh panel is 7.46
`M+S` per scalar. A 5,000-resample paired bootstrap of the 256 saved
savings, seeded `20261007`, gives a **descriptive input-variation**
interval of 6.03–9.02 units per scalar. It is not a timing interval.
The per-case choices, stage counts, source hashes, and zero-failure
rows are in `mixed-radix-scalar-result.json` (SHA-256
`51bb9c382b94d76d8a214f6ad16254c12c1abc3216662178a657ed5277ae844c`).

Independent checked Sage group replay recovered the expected public
point for **all 320 selected scalar outputs**, including 108 new
radix-two choices. Its receipt is `mixed-radix-sage-replay.json`
(SHA-256
`fe2ab79b27e5b3acf21d4a982b3aeed0dd5d783f98ca41a4dfe513cb2d0c64c1`).
An additional exact Eisenstein audit replays the signed-tripling
unit-gauge schedule with doubles interleaved and matches the short
representative on all 320 cases. It confirms the charged τ-pair count
of each selected radix-two stream; its receipt is
`mixed-radix-gauge-audit.json` (SHA-256
`54771a17a5c7d674d72d53a477d2a0f42fea07daf697da5a846d10e58ad77e76`).

These are **source-operation counts and correctness checks**, not a
native full-operation speed result. The per-scalar choice computes
both recoders, and that CPU work is excluded from `M+S`. A native
evaluator must reproduce the selected action stream, Jacobian doubles,
cheap τ pairs, caches, and final output before isolated wall timing.
Mixed-radix chains and endomorphism recoding already have prior art;
academic novelty remains unproved. This path is variable-time and
must not be used for secret scalars without separate work.

## Native evaluator replay

The native recoder, evaluator, Sage seed generator, and replay protocol
were frozen in `26e5f8f4` before release replay. The checked Sage
launcher generated **96 independent twelve-orbit seed points** for
the eight fresh bases; `mixed-radix-seed-fixture.json` has SHA-256
`bc5f1218f64edbf827080ea0ff26c1c27ea848bf754d752f1bfde538d1bfc3b2`.

The offline locked release build passed its original-path regression
and both selected mixed-radix panels. It checked 592 prepared points
and 64 final outputs on the design panel, then 2,381 prepared points
and 256 final outputs on the fresh panel. Every per-case greedy and
selective source count and chosen arm matched the frozen Python
record. Each executed evaluator's operation recount matched the
selected source cost, and **zero cached additions** took an exceptional
branch. A subsequent cross-language action audit, frozen in
`d37162be`, checked the full ordered radix/digit stream on all **320
cases** using a compact FNV-1a regression fingerprint. This is a
noncryptographic differential check; the exact scalar outputs and
fixture hashes are the correctness certificates.

`native-mixed-radix-checks.json` retains the raw build and replay
commands, exit codes, output, compiler/host, source and fixture
hashes, and the release binary hash. Its SHA-256 is
`0cca2f5c1add960d8b66f1ca001c97d53a035ee9d29d1f63360cc2b0665e5035`;
the replayed macOS ARM64 binary SHA-256 is
`0f99c3a934cf374cd8d51ab82fdf35d1b9907e22cfca46681b98a747c84dc9bc`.
No native timing was taken, and the CPU speedup claim remains `null`.

The final offline replay, including action fingerprints, is
`native-mixed-radix-checks-v2.json` (SHA-256
`0e8a25d14b9016840e743f7863dbbedafff201e71024f0c7b9fa852ce73609e0`).
Its independent Python fingerprint file has SHA-256
`ebe915ee02d7b8c07870202e7cb90fe0e4fa55aa53e8b91a2ea9de13e1c30f01`.
The final replayed release binary SHA-256 is
`ef6282b4fe884764ac6973528f42775857a7fc7c17e9b43e6ab268713dd6c857`.
