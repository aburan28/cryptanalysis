# 256-bit paired-stride stage result

The stage comparison and its measurement boundary were frozen in
`e0f8024f` before the fresh scalar inputs were derived. The checked
Sage launcher reported `status: verified` against accepted runtime
manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`.
The input digest is
`ea85e35bb285d64f8813fd52a8a5ccedc21ee44cfca7c70de7b0683ea446e3ce`.
The raw per-case record and source hashes are in `stage-result.json`;
the separate `stage-runtime-info.json` has SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.

All 128 fresh scalar inputs on eight secp256k1 subgroup bases matched
Sage's independent `kP` in both arms. The arms shared every short
lattice pair and τ-adic unit digit stream. They also matched on 20,278
τ steps and 13,563 mixed digit additions. The candidate fused 5,073
adjacent τ pairs, including 3,376 multiplication-free paired Z scales.
It used 102 coordinate rotations versus 87 in the nonfused free-gauge
control.

| Frozen evaluator formula boundary | Control | Paired/gauge candidate |
| --- | ---: | ---: |
| Nominal field multiplications across 128 scalars | 189,703 | 181,269 |
| Saving against control | — | 8,434 (4.446%) |
| Saving per scalar, median | — | 65 |
| Saving per scalar, range | — | 50–82 |

Every case had a positive nominal saving. A descriptive paired
bootstrap with 10,000 resamples and fixed seed `0x45120261007`
gave a 95% interval of 64.79–67.02 saved multiplications per scalar
and 4.35%–4.54% for the aggregate-count ratio under this deterministic
input law. These intervals describe scalar-input variation; they are
not CPU timing uncertainty. `summarize_stage.py` reproduces the
intervals from the committed per-case rows.

The formula count excludes field squarings, exceptional additions,
short-lattice reduction, τ-adic recoding, digit preparation, table
lookups, branch costs, normalization and inversion, and all Sage/Python
overhead. This comparison does not establish a faster full scalar
implementation. Both saved records set `cpu_speedup_claim: null`.
Native 256-bit execution, complete cost accounting, host-isolated
timing, and prior-art analysis remain required before a speed or
novelty claim.
