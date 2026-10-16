# Norm-4033 Eisenstein radix for scalar-local multiplication

The scalar-local path can use `π = 64+ω = 65−τ`, whose hexagonal norm is **4033**. Its Horner action is six doublings, one order-three x rotation, and one projective addition. The [hash-guarded overlay](native_sparse_radix4033_overlay.py) also changes the nearest-digit selector, exact quotient matrix, and step count from 20 to 22. The quotient is cyclic with `τ ≡ 65 (mod 4033)`; primality of the norm is not required for the recorded division and replay. The [Lean module](Radix4033.lean) checks the norm, adjugate identities, exact quotient under the selector congruence, and rotation identity. Its [fresh pinned receipt](radix4033-lean-check.json) records five axiom audits.

The follow-on [Lean bounds module](Radix4033Bounds.lean) proves that a rounded candidate for every signed residue has norm below 4033. Any selector that chooses a no-larger norm inherits that bound. It then proves the quotient norm recurrence and shows that **22 exact selected steps** from the existing secp256k1 four-corner initial envelope reach norm at most **101**, placing both terminal coordinates strictly inside the native radius-100 table. The [fresh pinned receipt](radix4033-bounds-lean-check.json) records nine additional axiom audits with only standard Lean foundations. The final theorem states its selector-minimum, exact-quotient, and initial lattice hypotheses explicitly.

The [source-bound selector audit](audit_radix4033_selector.py) checks the exact native selector and quotient snippets in the archived source, then compares all **2,017** nonnegative signed residues against an independent exhaustive lattice minimum. Negation covers the other 2,016 residue classes. All 4,033 classes satisfy the quotient congruence; the maximum selected-digit norm is **1,323** and coordinate magnitudes are at most **63** and **42**. The [receipt](radix4033-selector-audit.json) retains source and provenance hashes. Formal refinement of the executed signed-limb arithmetic, selector loop, and curve group operations remains open.

| Mathematical result | Lean declaration | Hypotheses and status |
| --- | --- | --- |
| Radix norm and quotient adjugate | `Radix4033.radix_norm`, `adjugate_first`, `adjugate_second`, `exact_quotient` | Checked; `exact_quotient` assumes the stated congruence. |
| Uniform digit bound | `Radix4033Bounds.rounded_digit_norm_below_radix`, `selected_digit_norm_below_radix` | Checked for residues `0..2016`; selector theorem assumes the selected norm is no larger than the rounded candidate. |
| Terminal coverage | `Radix4033Bounds.terminal_from_verified_digit_steps` | Checked under the secp256k1 four-corner equations, exact per-step quotients, selector bound, and norm tracking; gives coordinates in `(-100,100)`. |
| Executed selector and point arithmetic | Source audit and full-fixture replay | Empirically checked on the stated finite domains; Lean refinement to executed Rust remains open. |

## Paired Tier 1 measurements

The committed [one-scalar](tier1-radix4033-1-cpu40-manifest.json) and [128-point](tier1-radix4033-128-cpu40-manifest.json) plans compare norm 4033 with the norm-7009 rotated path on identical inputs, CPU 40, and 16 alternating repeats with adjacent A/A controls. Their [rules](tier1-radix4033-1-cpu40-rules.json) and [rules](tier1-radix4033-128-cpu40-rules.json) freeze the `[0.90,1.11]` noise gate and paired interval criterion. The Rust interval includes recoding, graph digit synthesis, and Horner evaluation; process launch, fixture loading, and external replay are outside it.

| Workload | Norm-7009 mean | Norm-4033 mean | Qualified paired reference/candidate median | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| One scalar | 0.542 ms | 0.471 ms | 1.140× | [1.130, 1.144] |
| 128 points | 39.500 ms | 38.959 ms | 1.017× | [1.010, 1.019] |

The [independent auditor](analyze_tier1_radix4033.py) checked source and binary hashes, every command/stdout/stderr and pair record, independent scalar replay of measured points, stable artifacts, and all A/A controls. Each panel completed **96 valid arms and 48 valid pairs**. The [one-scalar launch](tier1-radix4033-1-cpu40-launch.json), [audit](tier1-radix4033-1-cpu40-audit.json), and [raw archive](radix4033-1-raw.tar.gz) identify job `5198a67ca1fb418884feeb1585ad7d67`; the [128-point launch](tier1-radix4033-128-cpu40-launch.json), [audit](tier1-radix4033-128-cpu40-audit.json), and [raw archive](radix4033-128-raw.tar.gz) identify job `8fd7116208d94dee871413c6e33b4859`. The [native provenance](radix4033-native-provenance.tar.gz) carries both exact source trees, binaries, overlays, fixture, and build output. The initial [128-point correctness pilot](tier1-radix4033-128-pilot-cpu40-launch.json) and [raw record](radix4033-128-pilot-raw.tar.gz) are retained separately.

## Full-fixture replay

The separately [frozen manifest](tier1-radix4033-full-replay-cpu40-manifest.json) and [rules](tier1-radix4033-full-replay-cpu40-rules.json) sent two identical candidate arms through the serial queue. Job `1d3cf18c0fc94bf3b4c9646d783156f2` verified all **12,288** frozen outputs in each arm with stable artifacts. The [auditor](analyze_tier1_radix4033_full_replay.py), [launch](tier1-radix4033-full-replay-cpu40-launch.json), [audit](tier1-radix4033-full-replay-cpu40-audit.json), and [raw archive](radix4033-full-replay-raw.tar.gz) preserve the exact run. The two intervals were **3.652 s** and **3.670 s**. This A/A correctness run has a null speedup field.

The one-scalar gain is measured on the recorded Tier 1 cloud instance. Replication on another allocation and source-level arithmetic refinement are the next gates for a broader algorithmic claim.
