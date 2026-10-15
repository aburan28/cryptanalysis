# Norm-110557 Eisenstein digit radix

The radix-15 variant selects the Eisenstein digit prime `π = 334 - τ` with `τ² = 3τ - 3` and `N(π) = 110557`. Its 15 full two-x digit rows and terminal table retain **27,429,548 bytes**, below the 32 MiB cap. The frozen implementation reproduced all 12,288 independently computed secp256k1 scalar points on the same unseen uniform fixture used by the norm-136531 cache candidates. The [serial Tier 1 panel](tier1-alt-radix-cpu40-manifest.json) paired it with the norm-136531 ten-row cache under the [frozen acceptance rules](tier1-alt-radix-cpu40-rules.json). Its 96 arms and 48 pairs completed with stable artifacts; one A/A control missed the predeclared range, so the timing aggregate is unknown.

## Recoding and table geometry

Write a scalar-lattice representative as `a + bτ`. For the chosen `π`, reduce `a + 334b` modulo `110557` and choose a nearest digit `d_a + d_bτ` in that residue class. Set `k = (a - d_a + 334(b - d_b))/110557`. The quotient coordinates are

`a' = 331k - (b - d_b)`, `b' = k`.

The identity `(334 - τ)(a' + b'τ) = (a - d_a) + (b - d_b)τ` follows from `τ² = 3τ - 3`. The pinned [Lean module](AlternateRadix.lean) checks the exact quotient identity, `N(334-τ)=110557`, the no-small-divisor certificate, and the factor definition of primality. It also proves pair-norm nonnegativity, norm scaling by the digit prime, and the weighted inequality `100Q(z-d) ≤ 101Q(z)+10100Q(d)`. Its 15-step recurrence theorem shows that an initial norm at most `7·2^260` and digit norms at most `110557` force terminal norm below 5,000; the resulting upper bound is 3,443. The [build output](alternate-radix-lean-check.log) includes `#print axioms`; the selector-corner theorem uses the standard `propext`, `Classical.choice`, and `Quot.sound` foundations, while the other listed structural theorems use `propext` and `Quot.sound`.

The digit-norm premise has an elementary bound that avoids relying on the exhaustive maximum. Put `N=110557`, let `r` be a signed residue with `0≤r≤(N−1)/2`, and set `b₀=round(665r/(2N))`, `a₀=r−334b₀`. For `e=2Nb₀−665r`, nearest rounding gives `|e|≤N`. The exact identity `4NQ(a₀,b₀)=e²+3r²` and the resulting bound `Q(a₀,b₀)<N` are checked in Lean as `digit_candidate_norm_identity` and `rounded_digit_norm_below_prime`. The native selector searches this candidate and takes the minimum norm, giving `Q(d)<N` for every signed residue; Lean checks that implication in `selected_digit_norm_below_prime` under the stated minimum-norm premise. The [digit screen](screen_alt_digit_prime.py) checks the candidate identity, rounding bound, and selected-digit comparison for every residue. `quotient_norm_step_from_selected_digit` then proves the per-step norm recurrence from that digit bound and an exact quotient equation.

The [independent digit screen](screen_alt_digit_prime.py) exhaustively enumerates the 55,279 signed residue representatives, checking the congruence and rotation norm for each. Its [record](alt-digit-geometry.json) reports maximum digit norm 36,631 and 18,427 sign/rotation seeds including zero. The terminal construction uses `|a|,|b| ≤ 100` and norm below 5,000; it has 14,901 points and 3,025 orbit seeds including zero. The native replay reached this terminal domain for every frozen input. Lean now proves that a four-corner selector output lies within the 130-bit coordinate envelope under exact floor-remainder and basis-coordinate hypotheses, that this envelope implies `Q(a,b)≤7·2^260`, that a minimum-norm digit has `Q(d)<110557`, and that fifteen exact selected-digit quotient steps end below 5,000. The theorem `terminal_from_verified_digit_steps` exposes each residue, selection, quotient, and norm-tracking obligation for a fixed-limb implementation. The current implementation asserts the terminal bound when recoding; connecting its actual arithmetic and selector to those Lean hypotheses remains open.

The four-corner selector also has a direct coordinate envelope. Its lattice basis is `W=(671331852483699643819086596696745227419,−367917413016453100223835821029139468248)` and `V=(−238911465918039986966665730306072050094,303414439467246543595250775667605759171)`, with determinant equal to the scalar order `n`. Let `q_w=floor(kV₁/n)` and `q_v=floor(−kW₁/n)`. The identity `k(1,0)=(kV₁/n)W+(−kW₁/n)V` shows that every offset `(d_w,d_v)∈{0,1}²` yields `a+bτ=αW+βV` with `−1≤α,β<1`. Thus `|a|≤|W₀|+|V₀|=910243318401739630785752327002817277513<2^130` and `|b|≤|W₁|+|V₁|=671331852483699643819086596696745227419<2^130`. The [constant screen](screen_selector_corner_bound.py) checks the determinant, subgroup congruences, equal basis norms, and these strict margins. Lean proves the same bound in `selector_corner_coordinate_bound` under exact remainder and coordinate equations. Its `terminal_for_selector_corner` theorem composes the bound with the 15-step recurrence under an explicit per-step hypothesis. The fixed-limb reciprocal extraction, corner-certification dispatch, and digit-selection link to those hypotheses remain to be formalized.

| Result | Lean declaration | Status |
| --- | --- | --- |
| Exact quotient by `334−τ` | `quotient_step` | Checked |
| Centered-error identity for the candidate digit | `digit_candidate_norm_identity` | Checked |
| Rounded digit norm and selected-digit implication | `nearest_digit_rounding_error`, `rounded_digit_norm_below_prime`, `selected_digit_norm_below_prime` | Checked for every signed residue under the minimum-norm premise |
| Norm contraction for the selected digit | `quotient_norm_step_from_selected_digit` | Checked under exact quotient and minimum-norm hypotheses |
| Four-corner coordinate envelope | `selector_corner_coordinate_bound` | Checked under exact remainder and coordinate equations |
| Initial norm at most `7·2^260` | `selector_initial_norm_bound` | Checked from the coordinate envelope |
| Terminal norm below 5,000 after 15 selected-digit steps | `terminal_from_verified_digit_steps` | Checked under exact selector, residue, norm-tracking, and quotient hypotheses |
| Fixed-limb reciprocal extraction, corner dispatch, actual digit-selection minimum, and 15-step implementation composition | — | Open |

## Native recoder audit

The [digit-selector audit](audit_native_alt_digit_selector.py) extracts the actual `nearest_alt_split_prime_digit` function and constants from the hash-pinned native provenance archive, compiles them with Rust 1.93.1, and compares every signed residue with the independent Python digit construction. Its [receipt](native-alt-digit-selector-audit.json) records **55,279 outputs, zero mismatches**, maximum digit norm 36,631, the archived source hash, extracted selector hash, harness and binary hashes, and stdout digest. This directly checks the implementation's minimum-norm selection for every table index.

The [signed-limb step audit](audit_native_alt_unit_step.py) extracts the same selector and the exact `Signed192` addition, subtraction, small-radix division, small-factor multiplication, and `alt_split_prime_unit_step` methods from the frozen Rust sources. It compares each native next coordinate and folded digit index against independent integer quotient arithmetic for all **110,557 residues**, 121 coordinate edge combinations, and 4,096 seeded 130-bit coordinate pairs. Its [receipt](native-alt-unit-step-audit.json) records **114,774 cases, zero mismatches** and source, harness, input, binary, and stdout digests. Both audits are correctness checks; the pinned Rust source and finite cases support the implementation link while the Lean theorem still states its exact per-step hypotheses explicitly.

Reproduce these receipts from this directory with `python3 audit_native_alt_digit_selector.py` and `python3 audit_native_alt_unit_step.py`. Both scripts verify the native archive SHA-256 before extracting code.

The [hash-guarded overlay](native_alt_radix_overlay.py) applies to the frozen norm-136531 native source and builds the new rows using `334G - τG` as the successive base. It retains the same two-x orbit selection and affine layer reduction. The exact source, binary, failed first assertion receipt, corrected build, and replay are preserved in the [native provenance archive](alt-radix-native-provenance.tar.gz), SHA-256 `38194c291c28fe76efd057cdb6f08c60784e0ce9bc0c5dbdadea9cc9113b7090`. The first assertion failure came from a draft overlay that still used the prior `371` digit coefficient; the corrected hash-guarded overlay uses `334` in both digit selection and window-base advance.

## Measurement boundary

Each panel arm performs 96 batches of 128 distinct SHAKE256-derived scalar multiplications, with table construction and fixture loading outside Rust `Instant`. Every output is checked against independent binary multiplication after the interval. The worker serializes jobs, pins execution to CPU 40, and records exposed cloud-instance topology, cgroup limits, throttling, steal time, memory, and adjacent A/A controls. This is Tier 1 batch-throughput evidence; the result status follows the frozen A/A and paired-interval gates.


## Serial panel

The completed job `51a80dfd759e4d5e8d5196a0a031aa78` has [raw arms and pair records](alt-radix-tier1-raw.tar.gz), SHA-256 `fe6bf3c7aa5334cfbfdce606b31000e28876ba00857ef49fdd7b43c6d31cbcdd`. The [independent audit](tier1-alt-radix-cpu40-audit.json) verified the manifest, source and binary hashes, exact replay, all 96 arm outputs, all 48 pairs, and the predeclared gates.

| Tier 1 uniform scalar stream; 12,288 outputs per arm | Norm-136531 ten-row cache | Norm-110557 full two-x |
| --- | ---: | ---: |
| Retained table bytes | 33,318,020 | 27,429,548 |
| Mean timed interval | 66.625558 ms | 65.244457 ms |

The descriptive median paired reference/candidate ratio was `1.019807`, with paired bootstrap 95% interval `[0.995605,1.041598]`. The A/A control after comparison in repeat 4 measured `0.830042`, outside `[0.90,1.11]`. The aggregate remains `unknown_after_tier_gate`; its qualified comparison ratio is `null`.

## Longer serial panel

The [predeclared ten-pass rules](tier1-alt-radix-long10-cpu40-rules.json) and [manifest](tier1-alt-radix-long10-cpu40-manifest.json) were committed before result inspection. Each arm warms one table, then times ten passes over the same frozen 96 batches of 128 distinct scalars: 122,880 checked outputs per arm, with fixture loading and table preparation outside `Instant`. Both binaries use the same timing boundary, CPU 40, fixture, serial worker, and 32 MiB table cap. The [launch receipt](tier1-alt-radix-long10-launch.json) fixes job `14dd3766e7d643e380872b915398ce96` and the uploaded manifest/rules hashes.

The completed Tier 1 job recorded 96 valid arms and 48 valid pairs with stable artifacts. Its [independent archive-backed audit](tier1-alt-radix-long10-cpu40-audit.json) checked every raw arm, matched the source and binary hashes in the [native provenance archive](alt-radix-long10-native-provenance.tar.gz), and verified the [raw result archive](alt-radix-long10-tier1-raw.tar.gz). The provenance SHA-256 is `1f1cc52fb05fab292d9bc88982361af11c4ce0c70524138750062db7759503be`; the raw archive SHA-256 is `7435b737bb3591679fd9b9589759444b509f7ec48c6ec27bb382a7b301b5ed63`.

| Tier 1 ten-pass stream; 122,880 checked outputs per arm | Norm-136531 ten-row cache | Norm-110557 full two-x |
| --- | ---: | ---: |
| Retained table bytes | 33,318,020 | 27,429,548 |
| Mean timed interval | 670.434174 ms | 667.829651 ms |

The descriptive median paired reference/candidate ratio was `0.998244`, with paired bootstrap 95% interval `[0.965751,1.036469]`. The A/A control after comparison in repeat 6 measured `1.111348`, above the frozen upper limit `1.11`. The result status is `unknown_after_tier_gate`, with qualified comparison ratio `null`. The longer interval therefore supplies a tighter cost-shape screen for this batch path while preserving the failed control and every valid arm. Reproduce the audit with `python3 analyze_tier1_alt_radix_long10.py`; it extracts the raw archive when no local run directory is present.

## Prefetched affine table gather

The x86-64 [prefetch overlay](native_alt_prefetch_overlay.py) recodes all sixteen windows before gathering their affine entries, then prefetches offsets 0 and 64 of each selected 96-byte entry. Its portable path and table representation remain the same. The [frozen Tier 1 rules](tier1-alt-prefetch-cpu40-rules.json), [manifest](tier1-alt-prefetch-cpu40-manifest.json), and [launch receipt](tier1-alt-prefetch-launch.json) fix the source and binary hashes, 32 MiB cap, CPU 40, ten-pass fixture, sixteen repeats, alternating case order, and adjacent A/A acceptance interval `[0.90,1.11]` before result inspection.

Job `1445ccaffbf7479793ef49eb9005730e` completed 96 valid arms and 48 valid pairs with stable runner artifacts. Each arm checked 122,880 outputs after its timed interval. The [archive-backed audit](tier1-alt-prefetch-cpu40-audit.json) matched every stdout record and expected point, the sealed [raw records](alt-prefetch-tier1-raw.tar.gz), and the exact source, fixture, and binaries in the [native provenance archive](alt-prefetch-native-provenance.tar.gz). Their SHA-256 digests are `269d2cc2525b48bb75c47d0ecad674e2f12c3243c6c844134babda0fefc0f9cc` and `d7a9cd83f0722cfae10fc540a7b2f18f2109d5a1b20eebeb6a62b4a5caf4a907`, respectively.

| Tier 1 ten-pass stream; 122,880 checked outputs per arm | Baseline gather | Prefetched gather |
| --- | ---: | ---: |
| Retained table bytes | 27,429,548 | 27,429,548 |
| Mean timed interval | 622.543735 ms | 573.521775 ms |

The descriptive median paired baseline/prefetch ratio is `1.086784`, with paired bootstrap 95% interval `[1.037856,1.117295]`. The before-comparison A/A control in repeat 7 measured `0.866888`, outside the frozen range. The aggregate is therefore `unknown_after_tier_gate`, with qualified comparison ratio `null`. This panel establishes exact replay and a promising cost shape for the prefetch path; a fresh independently frozen panel and passing A/A controls are needed to resolve its timing. Reproduce the audit with `python3 analyze_tier1_alt_prefetch.py`.

### Independent prefetch replication

The [replication plan](tier1-alt-prefetch-rep2-plan.json) and [launch receipt](tier1-alt-prefetch-rep2-launch.json) committed the unchanged manifest and acceptance rules before job `b773ba315139428ab2d5935a9c848b33` ran. The second job was audited alone; its pairs were not pooled with the earlier failed-gate panel. It completed 96 valid arms and 48 valid pairs with stable artifacts and exact replay. The [precommitted auditor](analyze_tier1_alt_prefetch_rep2.py) checked the sealed [raw records](alt-prefetch-rep2-tier1-raw.tar.gz), SHA-256 `a12641bbba9e9859273303b00e1253676bbb5debfbcb49a77ab503f22e5cce1b`, against the unchanged [native provenance archive](alt-prefetch-native-provenance.tar.gz), SHA-256 `d7a9cd83f0722cfae10fc540a7b2f18f2109d5a1b20eebeb6a62b4a5caf4a907`.

| Tier 1 ten-pass stream; 122,880 checked outputs per arm | Baseline gather | Per-scalar prefetch |
| --- | ---: | ---: |
| Retained table bytes | 27,429,548 | 27,429,548 |
| Mean timed interval | 636.302152 ms | 565.837533 ms |

Every adjacent A/A ratio passed `[0.90,1.11]`. The paired median baseline/prefetch ratio is **`1.123359`**, with predeclared paired bootstrap 95% interval **`[1.083259,1.169518]`**. The [audit receipt](tier1-alt-prefetch-rep2-cpu40-audit.json) records `tier_gate_passed: true`, `aggregate_status: qualified`, and the preserved earlier failed-gate result remains separate. This is a qualified Tier 1 batch-throughput improvement for the exact ten-pass stream on the observed RunPod instance, with table preparation and fixture loading outside the timed interval.

## Eight-lane wavefront gather

The [wavefront overlay](native_alt_wavefront_overlay.py) separates recoding, prefetch, and affine gather across chunks of eight scalar inputs. It uses the same 15 digit rows, terminal table, two-x entries, and affine reduction as the per-scalar prefetch path. The [exact-replay smoke receipt](wavefront8-smoke.stdout) verified 122,880 outputs on the frozen fixture with 27,429,548 retained bytes. The [predeclared rules](tier1-alt-wavefront8-cpu40-rules.json), [manifest](tier1-alt-wavefront8-cpu40-manifest.json), [launch receipt](tier1-alt-wavefront8-launch.json), and [auditor](analyze_tier1_alt_wavefront8.py) were committed before panel results existed.

Job `d726b8604ac44cbda6612f7906844d8a` completed 96 valid arms and 48 valid pairs with stable artifacts. The [audit](tier1-alt-wavefront8-cpu40-audit.json) checked every output and expected point against the sealed [raw archive](alt-wavefront8-tier1-raw.tar.gz) and exact source and binaries in the [native provenance archive](alt-wavefront8-native-provenance.tar.gz). Their SHA-256 digests are `98fb61ecc74825e5b401892573ffe613c629c053613b606a687a360995635d7d` and `d041f28879788c8bc5fbf3712bbb62f05ccade0e55de125fca49ebf3cdb00cfc`.

| Tier 1 ten-pass stream; 122,880 checked outputs per arm | Per-scalar prefetch | Eight-lane wavefront |
| --- | ---: | ---: |
| Retained table bytes | 27,429,548 | 27,429,548 |
| Mean timed interval | 564.105001 ms | 566.963761 ms |

All adjacent A/A controls passed the frozen `[0.90,1.11]` range. The descriptive median prefetch/wavefront ratio was `1.002449`, with paired bootstrap 95% interval `[0.988639,1.010655]`. The Tier 1 noise gate passed, but the paired interval spans one, so the aggregate status is `unknown_after_tier_gate` and qualified comparison ratio is `null`. The eight-lane schedule has no resolved timing advantage in this panel. Reproduce the audit with `python3 analyze_tier1_alt_wavefront8.py`.
