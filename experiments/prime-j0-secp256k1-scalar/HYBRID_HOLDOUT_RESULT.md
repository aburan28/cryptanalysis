# Fresh fixed-hybrid τ alphabet result

The held-out source and protocol were frozen in `d1e06790` after the
training result selected mask 31, and before the fresh inputs were
derived. The checked Sage launcher reported `status: verified`, Sage
`10.10.rc0`, accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and runtime receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The new input digest is
`6ece5e8994142dc8dfa3e85416c763f8c94e8971dc7f48d404f9742ce2ba7348`.
The raw case-by-case inputs, digits, prepared-point sets and digests,
source hashes, and outputs are in `hybrid-holdout-result.json`.

All 64 fresh single-use secp256k1 base/scalar pairs passed exact
ring-digit reconstruction and independent Sage point checks in each
of the pure width-three, fixed-hybrid, and pure width-four arms.
Each arm built only the dependency closure of its actually used seed
points, batch-normalized the used points with one inversion, and
used prepared unit orbits for cheap paired τ strides.

| 64 one-use scalars; generic `M+S`, inversion separate | Width three | Fixed hybrid | Width four |
| --- | ---: | ---: | ---: |
| Digit additions | 2,953 | 2,410 | 2,311 |
| Constructed seed points | 128 | 447 | 510 |
| Paired τ strides | 4,011 | 4,699 | 4,791 |
| `M+S` excluding inversion | 87,347 | 85,367 | 85,433 |
| Field inversions | 64 | 64 | 64 |

The fixed hybrid saved **66 `M+S` units across 64 scalars** versus
width four, or **1.03 per scalar**. It won 34 paired cases, tied four,
and regressed in 26; per-case differences ranged from −57 to +34.
The 32-case training advantage was 9.19 units per scalar, so the
fresh result shows substantial shrinkage. A descriptive 10,000-fold
paired bootstrap with fixed seed `0x20261007` puts the mean saving's
95% interval at **−3.44 to +5.23** `M+S` units per scalar.
`summarize_hybrid.py` reproduces that interval. It describes
variation over this input law, **not CPU timing uncertainty**.

The prototype's 64-mask training search was performed once offline;
the selected runtime recoder uses a fixed alphabet and one pass.
Its ring operations, branches, table lookup, allocations, and
preparation control flow are excluded from the model. The tiny and
uncertain arithmetic difference cannot pay for a novelty or speed
claim. The fixed hybrid is **not promoted** into the scalar path.
`cpu_speedup_claim` and `academic_novelty_claim` remain `null`.

The [published width-four method](https://eprint.iacr.org/2024/1906)
and the repository's earlier width-three recoder are the controls.
Variable-window scalar recoding has related work; absence of an
identical rule from a limited literature search does not establish
academic novelty. The next design needs a larger structural gain
that survives a fresh one-use comparison after preparation and
recoding are charged.
