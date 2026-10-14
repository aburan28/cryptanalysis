# secp256k1 paired-τ formula check

The validation script and protocol were frozen in `0c18e29d` before
execution. The checked repository Sage launcher reported status
`verified`, Sage `10.10.rc0`, and accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`.
The complete launch record is `runtime-info.json` (SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).

The secp256k1 check passed for 64 deterministic nonzero subgroup
points. Each point was encoded under three Jacobian scales. Sage's
elliptic-curve group operations verified 192 τ outputs, 192 tripling
outputs, all 576 paired-τ outputs across the three carried-gauge
changes, and 64 instances of `τ²(P) = -3ω(P)`. The input-point SHA-256
is `d8e4efcf3a778a01e1d60889c2366dc33695adfe916935766890b86f587500f6`.
The exact field, subgroup, cube root, source hash, and check counts are
in `result.json`.

This confirms that the small-field C formulas used by the paired-τ
candidate are mathematically compatible with secp256k1's 256-bit
field. The script does not execute the C arithmetic at 256 bits or
validate the full τ-adic scalar recoder there. It has no wall-time
comparison, and `cpu_speedup_claim` is `null`. A full 256-bit scalar
implementation and controlled isolated-host measurement remain open.
