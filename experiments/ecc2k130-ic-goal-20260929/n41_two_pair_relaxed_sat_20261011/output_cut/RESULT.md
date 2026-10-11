# Supplied-output N41 completion by two group differences and linear solves

Fixing one known-positive pair-output reciprocal in the exact N41 two-pair
formula still left both a positive and an exhaustively classified negative
residual **`BOUNDED_UNKNOWN`** at a 30-second CryptoMiniSat limit. Replacing
the remaining Boolean search with two target-dependent group differences
and two 18-column GF(2) solves classified the positive as
`RELAXED_SUM_HIT` and the negative as `COMPLETE_RELAXED_NO_SUM`. Independent
checked Sage replay verified the curve arithmetic, binary linear ranks,
the positive pair equation, and the exact group sum.

This is a validation cut on the [implicit relaxed two-pair
circuit](../RESULT.md). The supplied left reciprocal
`z_L=1606734567992` comes from its separately replayed positive witness;
it is fixed in both queries. The same frozen residual points are used:
`M_+=(1385030211012,1839474220645)` and
`M_0=(1552521799954,1663016718497)`. Both signs of the left point are
considered. The factor-base search that would generate a useful first
output from an ordinary public point is outside this cut.

The 41 unit clauses fix only `z_L` in the [SAT cut](cut.py); seed-sum,
product, branch, and right-output variables remain free. The known complete
assignment passes all 11,439 CNF clauses and 2,026 XOR rows of the positive
formula. The [frozen protocol](protocol.json) binds the source, supplied
coordinate, targets, solver binary, one-worker flags, 30-second internal
limit, 35-second parent limit, and 4 GiB RSS cap. Both unpinned cut formulas
were rebuilt byte-for-byte in the [terminal audit](audit.json), which also
confirms active search before their parent wall stops.

For the [list-free completion oracle](linear_oracle.py), lift the supplied
`z_L` to its two curve signs `L`. For each sign, compute `R=M-L`; if
`z_R=1/x(R)` has trace zero, solve the right pair equation

`p*z_R + H((s+z_R)²) + epsilon = 0`

as a 41-row binary linear system in six seed-sum bits, eleven product-span
bits, and one branch bit. A consistent affine solution with nonzero seed
sum is exactly a member of this relaxed pair domain. The implementation
checks the resulting equation and group sum before returning a hit. Its
[protocol](linear_protocol.json) froze the source and both inputs before
measurement, and the [Sage replay](sage_replay.json) independently checked
all four sign-specific rank and membership decisions using the repository's
verified [Sage runtime](sage_runtime_info.json).

| Supplied-output residual | SAT cut, solver process | Linear oracle, target-dependent interval | Exact outcome |
| --- | ---: | ---: | --- |
| Positive | 35.118 s; `BOUNDED_UNKNOWN` | 10.503 ms | one sign hits; rank 18/18, seed sum 7, product mask 6 |
| `control_0` | 35.129 s; `BOUNDED_UNKNOWN` | 9.086 ms | both signs rejected; rank 18/18 |

The CPU intervals are exploratory on an unisolated host; the algorithmic
difference is the exact replacement of an open Boolean search by two group
subtractions and two small linear systems **once a first pair output is
supplied**. The prior N131 W18 supplied-coordinate inverse provides the
analogous local operation at challenge width, while the first-output
generation and four-pair public-target coupling remain the active gates.
This component has `candidate_id: null` and does not measure ordinary N131
relation yield or a single-target IC online time.
