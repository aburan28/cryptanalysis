# Zero-τ priority rule: source and Sage panel

The eight-rule retrospective screen, chosen zero-τ recoder, new Sage
fixture generator, independent group validator, and protocol were frozen
in local commit `15d634fd` **before** generating the new fixture. The
original 64-case panel was design data. The checked repository Sage
launcher reported `status: verified` in `zero-tau-runtime-info.json`
(SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).

The new fixture has eight bases and 32 scalars per base, all distinct
and with zero scalar overlap against the six prior local fixtures. A
separate cross-branch check found zero scalar or base/scalar-pair overlap
with the exact-radix fixture (SHA-256
`05c71e0bd5426eefa46b934ebef4ce6622a6d859a61962a3274390f4654dc36f`).
The new input digest is
`4c417489519c4580426d7d8f9e6bb9ff481ef632430e198bfec8bb79cad9f455`;
`zero-tau-fixture.json` has SHA-256
`9018f9a560648080d069ec9eed34a9b066808bb327a354db5cecd19534229243`.

| Panel | Cases | Previous selector `M+S` | Zero-τ selector `M+S` | Saving |
| --- | ---: | ---: | ---: | ---: |
| Retrospective design | 64 | 86,711 | 86,405 | 306 (0.353%) |
| **New Sage fixture** | **256** | **347,455** | **346,289** | **1,166 (0.336%)** |

The zero-τ arm was chosen for 132 fresh cases and the selective arm for
124. Against the previous per-scalar selector on identical inputs,
132 cases improved, 124 tied, and none regressed. The mean modeled
saving is 4.55 `M+S` per scalar. A 5,000-resample paired bootstrap,
seeded `20261007`, gives a **descriptive input-variation** interval of
3.92–5.22 units per scalar, not a timing interval. All rows and
source hashes are in `zero-tau-paired-source.json`; the zero-τ action
digests and operation components are in `zero-tau-result.json` (SHA-256
`8f00f620f0c9fac7116fee56077facf0b60d3a64b9353fff2b2088ba92fc3116`).

The recoder had no cycles or length-limit failures on either panel.
Its fixed-digit τ map has maximum Eisenstein digit norm 76. The
closed norm-152 region contains 559 integer states, all of which
passed the termination audit. Independent checked Sage group replay
recovered the expected public point for all 320 selected design and
fresh streams, including all 132 fresh zero-τ choices. Its receipt is
`zero-tau-sage-replay.json` (SHA-256
`c19407a38714c53e1ebe35deedcfab2cd4355f5163f8b5f1262a16c66f3e5031`).

## Native replay and isolated timing handoff

The native recoder, evaluator, action fingerprint generator, Sage seed
generator, replay harness, and protocol were frozen in local commit
`2aa4154d` before release replay. The independent seed fixture contains
96 twelve-orbit points for the eight fresh bases and has SHA-256
`ea6b0ae24ea81ffad14cc51c017d3ca6c537692b4302041bfe230cb03b7ca732`.
The Python action fingerprint file has SHA-256
`c7b7d34310b792237109536f43b1099bea8545a84efcde2a8d09993b4b18b715`.

The offline release replay passed the original-path regression and all
**320 ordered zero-τ action fingerprints**, source counts, 2,947 checked
prepared seed points, and 320 expected public points. Every executed
operation recount matched its source record, and zero cached additions
took an exceptional branch. Untimed paired checks covered both selector
arms against the prior mixed-radix evaluator on identical inputs.
`native-zero-tau-checks.json` retains raw commands, outputs, exits,
compiler/host, source hashes, and the binary hash; its SHA-256 is
`f9a3729075d66d018da24757b754995bb214960ae931eb65df344a1cd7774c4a`.
The replayed macOS ARM64 binary SHA-256 is
`8de9768720873b34564353c385b64f9500ddd634c90d3cba81d2216ba05a286c`.

`make_zero_tau_manifest.py` builds a 256-case paired complete-operation
manifest against the earlier greedy-or-selective path. Both timers
include scalar/base decoding, lattice reduction, both relevant
recoders, selection, seed preparation, group evaluation, affine
conversion, formatting, and expected-point comparison. The isolated
runner's **structural schema** accepted the manifest with synthetic
CPU, NUMA, and cgroup values. The manifest SHA-256 is
`3b292651fc54e8def70d4dd47329567d377be52412a44e8a0734fa654c35706b`;
`zero-tau-manifest-schema.json` records that schema-only check. No
physical-host isolation preflight or timed comparison was performed.

The source saving does **not** establish a CPU speedup; that remains
unknown until a paired physical-host run. Mixed-radix and endomorphism
scalar methods have prior art; academic novelty is unproved. This path
is variable-time research code.
