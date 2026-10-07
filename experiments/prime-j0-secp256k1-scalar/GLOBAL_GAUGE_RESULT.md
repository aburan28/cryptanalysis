# Held-out global-gauge result

The source and protocol were frozen in `8e4c0285` before deriving the
fresh input set. The checked Sage launcher reported `status: verified`,
Sage `10.10.rc0`, accepted runtime manifest SHA-256
`0a27ddfece04798b893c0feef292caab7f30ce68440f4d18092fe6358ef5499a`,
and runtime receipt SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`.
The input digest was
`396cc29811138a94c5489e9fcde823ae13114bf5681dc9cc8233f2041dcc2d05`.
The raw per-case record and source hashes are in `global-gauge-result.json`.

All 128 held-out secp256k1 scalar outputs on eight bases matched
Sage's independent `kP` in both arms. The τ-step and mixed-add counts
were identical per scalar. The globally optimized schedule used the
same 5,081 fused pairs as the local policy. It made 4,519 of their
Z scales cheap, versus 3,380 for the local policy, but required 1,013
digit/final rotations, versus 106. Thus its 1,139 additional cheap
Z scales cost 907 additional rotations, for a net **232 nominal field
multiplications saved** across 128 scalars.

| Frozen evaluator formula boundary | Local policy | Global optimum |
| --- | ---: | ---: |
| Nominal field multiplications, 128 scalars | 181,225 | 180,993 |
| Saving against local | — | 232 (0.128%) |
| Cases with saving / tie / regression | — | 102 / 26 / 0 |

The gain averages 1.8125 nominal multiplications per scalar. The
search for the optimal schedule is excluded from the formula count,
and would add work to a real implementation. No CPU time was measured;
`cpu_speedup_claim` is `null`. This result does **not** justify
promoting global schedule search into the scalar path. Retain the
simple local policy unless a later complete native comparison shows
an advantage.

No case failed in this run. The frozen script asserts correctness and
would abort before writing a result file if a case failed; it does not
serialize a partial failure row. That is a limit of this diagnostic
runner and must be fixed before using it as a campaign measurement
collector.

The algebraic identity `ω²τ²=-3` also makes the cheap stride a signed
tripling. [Xu et al.'s existing optimized window method](https://eprint.iacr.org/2024/1906) already uses
tripling after moving unit factors into its digits. That limits the
novelty case for both the local and global variants. The control here
is the local policy for the same unit-digit evaluator, not the
published window method or a native GLV baseline.
