# Redundant tau-four digit screen

Two signed unit orbits per nonzero residue class modulo `tau^4` reduce the
source point-formula count for secp256k1 scalar multiplication. On 128 frozen
holdout scalars, a depth-two rollout uses 146,400 field-product proxy units,
compared with 150,896 for the same two-orbit table with its first digit chosen
at every step: a reduction of 4,496 units (2.98%). All 128 holdout cases
improved. This is a recoding and point-formula result; a native implementation
and controlled full-operation timing are the next measurements.

## Construction and termination

Represent an Eisenstein integer as `a + b tau`, where `tau = 1 - omega`,
`tau^2 = 3 tau - 3`, and `tau^4 = 9 omega^2`. The norm is
`N(a,b) = a^2 + 3ab + 3b^2`. A nonzero digit matches the current integer
modulo `tau^4`, so its four-step quotient is exactly
`omega * ((z - d) / 9)`. The digit table holds two signed unit-orbit
representatives for each of the 54 residue classes not divisible by `tau`.
The 18 seed pairs and every expanded digit are recorded in
[`redundant-tau4-result.json`](redundant-tau4-result.json).

The largest digit norm is 64. For a nonterminal nonzero state with norm
`N(z) > 1`, the quotient obeys
`N(q) <= (sqrt(N(z)) + 8)^2 / 81 < N(z)`. States of norm one are terminal.
At a zero digit, division by `tau` divides the norm by three. Thus every
digit choice terminates. The screen checks the residue, quotient identity,
norm decrease, and reconstruction for every visited state. Its unbounded
dynamic program is exact for the declared point-formula cost because all
transitions decrease the norm.

The bounded policy considers both digits for one, two, or three future
nonzero blocks, scores the remaining state with the fixed first-digit
continuation, and repeats the decision at the next state. The terminal
lookup accepts either precomputed digit. The policy with one digit per
residue accepts only that digit at termination. Every ordinary `tau` step
costs five field-product proxy units; each nonzero block costs four such
steps plus one mixed addition at eleven units, or 31 units. The proxy
counts source point formulas and excludes integer recoding, table setup,
lookup, memory traffic, and any device transfer.

## Frozen scalar panel

The first 86 scalars are the existing paired fixed-generator fixture:
22 edge cases and 64 random cases under seed `20261009`. A separate Python
`Random(20261013)` stream supplies 128 holdout scalars in `[1,r)`. The
existing native width-three fixed-base executable computes one Eisenstein
representative and point for each scalar. The screen checks the scalar
congruence modulo the secp256k1 order and compares the native point with
independent Python point multiplication before recoding. It then checks
reconstruction and the exact operation count of all six policies. The JSON
records each scalar, representative, policy counts, executable and source
hashes, and aggregate totals.

| Policy | 64 design random cases | 128 holdout random cases | Holdout saving vs dual first-digit |
| --- | ---: | ---: | ---: |
| One orbit per residue | 75,525 | 151,330 | -434 |
| Two orbits, first digit | 75,339 | 150,896 | reference |
| Depth-one rollout | 73,889 | 147,558 | 3,338 (2.21%) |
| Depth-two rollout | 73,294 | 146,400 | 4,496 (2.98%) |
| Depth-three rollout | 72,997 | 145,680 | 5,216 (3.46%) |
| Exact proxy optimum | 72,433 | 144,489 | 6,407 (4.25%) |

These totals count field-product proxy units over each panel. The exact
optimum is an operation-count bound for this fixed digit set and terminal
policy, not an execution-time bound. Depth-two rollout is the next practical
implementation target because it captures 70% of the holdout proxy saving
available from the exact dynamic program while limiting lookahead.

## Reproduction and next measurement

Build the native executable from the parent fixed-base work, then run:

```sh
cd experiments/prime-j0-secp256k1-native
cargo build --release
PYTHONDONTWRITEBYTECODE=1 python3 redundant_tau4_screen.py --output /absolute/path/to/new-result.json
```

The script refuses to overwrite an existing result. The checked-in result
has SHA-256 `9568fef212d18125bad82e87dd005e0e6a5a243215ec52d025fc05bb78ac05b2`.
The next implementation should expose both digit choices in the native
fixed-generator path, measure integer recoding and table cost, verify the
same point panel, and compare full scalar multiplication on a host whose
receipt passes the strict isolation preflight in
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).

The supplied Xu–Yu–Han–Lu manuscript gives a width-four single-representative
digit table. Redundant tau-adic digit sets and optimal recodings have earlier
literature; this screen specifies a secp256k1 two-orbit construction and
measures bounded rollout against that fixed table. Academic priority for the
exact construction remains to be checked against that literature.
