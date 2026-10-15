# A sparse Eisenstein radix family

The family `πₖ=(2ᵏ−1)+2ᵏτ`, with `τ²=3τ−3`, keeps the short point action `πₖP=[2ᵏ](P+τP)−P` while changing the digit-table size and recoding length. Its exact norm is `Nₖ=7·2²ᵏ−5·2ᵏ+1`, and the cyclic quotient has the explicit residue `τ↦4−7·2ᵏ` modulo `Nₖ`. These identities give a concrete design space around the measured `k=7` radix, including smaller tables that may improve one-scalar cold cost.

## Algebra and proof map

For an arbitrary integer `t`, define `πₜ=(t−1)+tτ`. Multiplication on an integer pair is

`πₜ(u,v)=((t−1)u−3tv, tu+(4t−1)v)`.

The [pinned Lean 4.34.1 module](SparseRadixFamily.lean) checks six results: `family_shortcut` proves the `[t](1+τ)−1` action; `family_norm` proves `N(πₜ)=7t²−5t+1`; `family_residue` proves `(t−1)+t(4−7t)=−N(πₜ)`; `family_residue_polynomial` proves the quotient root satisfies `s²−3s+3=7N(πₜ)` for `s=4−7t`; and `family_norm_scaling` proves `N(πₜz)=N(πₜ)N(z)` for every integer pair `z`. The sixth theorem, `radix64_terminal_from_norm_step`, proves that an initial pair norm at most `7·2²⁶⁰` and the explicit 17-step recurrence `100·28353·qᵢ₊₁ ≤ 101·qᵢ+10100·9451` imply `q₁₇<5000`. The recurrence and uniform digit cap are explicit hypotheses; their bridge to the finite selector remains open. The [fresh checker](check_sparse_radix_family_lean.py) and [receipt](sparse-radix-family-lean-check.json) retain the source hashes, actual successful builds, and `#print axioms` for each declaration. The proofs use the standard Lean foundations `propext`, `Classical.choice`, and `Quot.sound`.

## Exact recoding screen

The [integer screen](screen_sparse_radix_family.py) uses one frozen 12,288-scalar fixture, the same short-lattice selector, signed quotient residues, and exact integer division at every radix step. It independently reconstructs every original scalar pair from the selected digits and terminal pair. The fixture SHA-256 is `a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3`; the [receipt](sparse-radix-family-screen.json) retains each digit and terminal digest. The displayed step is the first count at which every fixture terminal pair has norm below 5,000 and both coordinates at most 100 in absolute value.

| `k` | Radix pair | Norm | Orbit-folded digit seeds | Fixture steps | Maximum terminal norm |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | `(31,32)` | 7,009 | 1,169 | 20 | 1 |
| 6 | `(63,64)` | 28,353 | 4,727 | 17 | 9 |
| 7 | `(127,128)` | 114,049 | 19,009 | 15 | 7 |

The `k=7` row reproduces the existing sparse-radix screen's 19,009 digit seeds, 15 steps, and maximum observed terminal norm 7. The selected step counts are exact for this fixture; a global termination and selector bound for `k=5` or `k=6` remains a separate proof obligation.

The [hash-guarded native `k=6` overlay](native_sparse_radix64_overlay.py) uses the exact quotient coefficients and a six-doubling point action. It independently verified the [one-scalar](sparse-tau64-pilot-1.stdout) and [12,288-point](sparse-tau64-pilot-12288.stdout) frozen fixtures. The untiered pilot retained **922,596 bytes**, prepared the table in **93.27 ms** for one scalar and **98.28 ms** for the full stream, and evaluated the full stream in **633.90 ms**. The executed windows SHA-256 is `499387980e4791085521f760809f3b3f49e21ee8f716f7f7b85f4202ce1e7b85`; the binary SHA-256 is `e6a46cd951c393d795564bbfa60c7a9d6eb08d5f454b906d3d9ef3330bed71cb`. The [build log](sparse-tau64-build.log) is retained.

The matched Tier 1 one-scalar cold panel, job `1ebc1b95247c45bb90c957bed33ba2b1`, completed 96 valid arms and 48 pairs with stable artifacts and passing A/A controls. The `k=7` reference averaged **255.34 ms** and `k=6` averaged **93.58 ms**, both including process-local table preparation and one scalar operation. The qualified paired `k=7/k=6` median is **2.7370**, with predeclared 95% bootstrap interval **[2.7252, 2.7390]**. The `k=6` table retains 922,596 bytes against 2,636,452 bytes for `k=7`. The [manifest](tier1-tau64-cold-cpu40-manifest.json), [rules](tier1-tau64-cold-cpu40-rules.json), [launch](tier1-tau64-cold-cpu40-launch.json), [auditor](analyze_tier1_tau64_cold.py), [audit](tier1-tau64-cold-cpu40-audit.json), [raw archive](tau64-cold-tier1-raw.tar.gz), and shared [native provenance](tau64-online-native-provenance.tar.gz) preserve the complete result. The raw archive SHA-256 is `7ddecb84b5d98f5642edcdde21ed9501b9ddb6ef6c08ab8f5856202a3a559b36`; the provenance archive SHA-256 is `9b2ee3aebadfe7b3474f3e27f2a35b7573af40076aa5b377de4494f3`.

The matched Tier 1 prepared-table panel, job `664fc7a36b064850ae1c103b186f057a`, measured one pass over 12,288 distinct frozen points in each of 16 repeats. All 96 arms and 48 pairs were valid, artifacts remained stable, and adjacent A/A controls passed. The `k=7` reference averaged **602.05 ms** and `k=6` averaged **624.66 ms** for the scalar operations after process-local table preparation. The qualified paired `k=7/k=6` median is **0.9637**, with predeclared 95% bootstrap interval **[0.9612, 0.9659]**. Thus the shorter `k=6` table cuts one-scalar cold latency and retained memory, while the `k=7` radix is faster for this prepared 12,288-point stream. These panels have different timed boundaries and are reported separately. The [manifest](tier1-tau64-online-cpu40-manifest.json), [rules](tier1-tau64-online-cpu40-rules.json), [launch](tier1-tau64-online-cpu40-launch.json), [auditor](analyze_tier1_tau64_online.py), [audit](tier1-tau64-online-cpu40-audit.json), and [raw archive](tau64-online-tier1-raw.tar.gz) preserve the result; raw archive SHA-256 is `075629e0445e5712ddf802cdca5e9cc19a6a39bc159e91ee234fe6dcd8bbb4bc`.
