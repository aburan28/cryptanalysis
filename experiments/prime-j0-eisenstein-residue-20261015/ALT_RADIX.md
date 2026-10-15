# Norm-110557 Eisenstein digit radix

The radix-15 variant selects the Eisenstein digit prime `π = 334 - τ` with `τ² = 3τ - 3` and `N(π) = 110557`. Its 15 full two-x digit rows and terminal table retain **27,429,548 bytes**, below the 32 MiB cap. The frozen implementation reproduced all 12,288 independently computed secp256k1 scalar points on the same unseen uniform fixture used by the norm-136531 cache candidates. The [serial Tier 1 panel](tier1-alt-radix-cpu40-manifest.json) paired it with the norm-136531 ten-row cache under the [frozen acceptance rules](tier1-alt-radix-cpu40-rules.json). Its 96 arms and 48 pairs completed with stable artifacts; one A/A control missed the predeclared range, so the timing aggregate is unknown.

## Recoding and table geometry

Write a scalar-lattice representative as `a + bτ`. For the chosen `π`, reduce `a + 334b` modulo `110557` and choose a nearest digit `d_a + d_bτ` in that residue class. Set `k = (a - d_a + 334(b - d_b))/110557`. The quotient coordinates are

`a' = 331k - (b - d_b)`, `b' = k`.

The identity `(334 - τ)(a' + b'τ) = (a - d_a) + (b - d_b)τ` follows from `τ² = 3τ - 3`. The pinned [Lean module](AlternateRadix.lean) checks the exact quotient identity, `N(334-τ)=110557`, the no-small-divisor certificate, and the factor definition of primality. It also proves pair-norm nonnegativity, norm scaling by the digit prime, and the weighted inequality `100Q(z-d) ≤ 101Q(z)+10100Q(d)`. Its 15-step recurrence theorem shows that an initial norm at most `7·2^260` and digit norms at most 36,631 force terminal norm below 5,000. The [build output](alternate-radix-lean-check.log) includes `#print axioms`; the structural theorems use only the standard `propext` and `Quot.sound` foundations.

The [independent digit screen](screen_alt_digit_prime.py) exhaustively enumerates the 55,279 signed residue representatives, checking the congruence and rotation norm for each. Its [record](alt-digit-geometry.json) reports maximum digit norm 36,631 and 18,427 sign/rotation seeds including zero. The terminal construction uses `|a|,|b| ≤ 100` and norm below 5,000; it has 14,901 points and 3,025 orbit seeds including zero. The native replay reached this terminal domain for every frozen input. The remaining formalization bridge is the existing scalar-lattice selector's 130-bit coordinate envelope and the exhaustive digit-set maximum as hypotheses of the recurrence theorem. The current implementation asserts the terminal bound when recoding; the full all-scalar formalization remains partial.

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
