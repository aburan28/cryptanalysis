# Fifteen-position `268−τ` prime-norm scalar radix

The prime-norm radix `268−τ` reaches a **15-position** fixed-base secp256k1 recoding with a nearest digit in each of 71,023 quotient residues. Within the declared exact `T=240…320` prime-norm sweep, it has the smallest direct point payload: **11,624,512 bytes**, with a terminal norm radius of 82. Its native table retains **12,336,756 bytes**. This trades more table memory and preparation for one fewer digit-position addition than the 16-position `190−τ` reference. The frozen direct Tier 1 comparison below measures the runtime effect.

For `τ²−3τ+3=0`, `N(268−τ)=268²−3·268+3=71,023`, which is prime. The six-candidate selector checks two residue lifts and three nearby `b` values per lift, minimizing `(norm, |b|, |a|, a, b)`. The wider global search agrees for all 35,512 sign-canonical residues under the norm-derived `|b|≤178` bound. Its maximum selected digit norm is 23,497. Fifteen radius contractions end below `82²`; the digit table has 11,838 six-unit orbit seeds, and the terminal table has 4,063.

| Evidence | Artifact |
| --- | --- |
| Exact 12-prime-norm 15-position shape sweep | [`frontier15.py`](frontier15.py), [`frontier15.json`](frontier15.json) |
| Global selector, radius, orbit, and 128-scalar integer replay | [`screen268.py`](screen268.py), [`screen268.json`](screen268.json) |
| Independent affine secp256k1 replay of 388 scalars | [`group_replay268.py`](group_replay268.py), [`group-replay268.json`](group-replay268.json) |
| Hash-guarded native overlay and build/test receipts | [`native268_overlay.py`](native268_overlay.py), [`linux-test.log`](linux-test.log), [`linux-build.log`](linux-build.log) |
| Frozen 15-versus-16 Tier 1 panel | [`tier1-rules.json`](tier1-rules.json), [`freeze_panel.py`](freeze_panel.py), [`tier1-manifest.json`](tier1-manifest.json) |

The shape sweep checks every selected residue, sign and six-unit covariance, the digit norm, every strict contraction inequality, and the full terminal lattice count. It records all twelve prime norms in the declared range, including the larger-terminal candidates `247−τ` and `248−τ`. The finalist screen additionally checks the six-candidate result against all congruent digits whose norm could improve it, and reverses every frozen 15-step integer recoding. Independent affine replay reconstructs points from the 15 window bases, the six-unit orbit action, and the terminal point, then compares all 388 results with binary scalar multiplication. It matches the frozen 17-position replay digest on the same points.

The native overlay checks parent source SHA-256 `e195374c4e6fde368bdba106c769c6335cd319f9f5547e8e2291089fe055335e` before editing, producing source `aff42df465e44e2f3fe1d10c524b6a336a76c5091791894cac5cba618cc441ee` and Linux release binary `979595ad1316aee2431f65cacb8ac1b71a70923d108cac3fafe6382a60d37cf9`. Its full 71,023-residue native test and independent-binary 128-case holdout passed. The release preflight internally verified all 12,288 repeated point outputs, recorded the same fixture and final point as the 16-position reference, and retained 12,336,756 bytes. The standalone 138.07 ms reading is a preflight, not a paired timing result.

The frozen panel pairs the 15- and 16-position binaries on the same 128 scalars and cloud allocation. It fixes CPU 13, 96 passes per arm, 16 alternating repetitions, adjacent A/A gates [0.90,1.11], binary and source hashes, and complete raw receipt retention. Both table preparation and retained bytes are reported separately from sustained hot-table throughput. Its isolation tier is the cloud-instance tier; the pod affinity mask does not establish host-wide physical isolation.

The arithmetic and 15-step bound have exact Python and native checks above. A faithful Lean 4 theorem for this candidate's radius contraction, selected digit, and point action is the next formalization step; the 17-position theorem's numeric certificate does not transfer to norm 71,023.
