# Fixed-width radix-943 coefficient recoder

The opt-in signed three-limb recoder replaces per-window `BigInt` remainder,
subtraction, and division in the implemented thirteen-window radix-943
fixed-base multiplier. It takes each 192-bit magnitude in six 32-bit chunks,
computes quotient and remainder together using constant 64-bit division, then
applies a signed one-digit quotient correction. The atlas, 1,926,717 point
slots, retained payload, unit actions, and mixed-addition sequence are shared
with the reference. The implementation improvement targets recoder cost in
the complete scalar operation.

The [frozen protocol](PROTOCOL.md) precedes the candidate implementation.
The [input record](inputs.json) holds seven boundary scalars and 512 reduced
full-range scalars from `Random(20261009413)`, with scalar-input SHA-256
`19cf3b254049899186791cc9873cea7d0715a422c7b495697c8e0f373605617b`.
The native test compares the fused quotient and every selected digit,
orbit/unit code, and post-window coefficient with the original `BigInt`
algorithm. It checks all 129 frozen fixture points, all 519 new input points,
and the first 128 new full-range points against a separate binary
double-and-add evaluator. Signed values around zero, 64-, 128-, and 191-bit
boundaries also compare exact quotients against `BigInt`.

| Verification gate | Result |
| --- | ---: |
| Native release tests | 62 passed |
| Reference fixture CLI results | 129 verified |
| Word candidate fixture CLI results | 129 verified |
| Fresh and boundary scalar output comparisons | 519 passed |
| Independent fresh binary scalar multiplications | 128 passed |
| Same-binary benchmark-case dispatches | 2 verified |
| Retained radix-943 payload in each mode | 142,873,744 bytes |

The [verification receipt](verification.json) binds the release binary,
executed source and input hashes, architecture/compiler, every command and
exit code, and [raw outputs](native-tests.stdout.txt). The separate
[isolated panel](ISOLATED_PANEL.md) has nine same-scalar cases and five
repetitions per case; its generator requires the source-bound checker receipt
and passed a local schema dry-run. The current RunPod CPU Pod fails the
host-level isolation preflight, so the complete online wall-time comparison
is pending a qualifying host. The local benchmark-case outputs are retained
as dispatch evidence rather than used as an online speedup ratio.

The next decision is the isolated paired online result, including recoding,
lookup, unit action, additions, and recovery check. If the new recoder reduces
that total, it can replace the `BigInt` path for public fixed-base scalars;
otherwise the reference remains the default.
