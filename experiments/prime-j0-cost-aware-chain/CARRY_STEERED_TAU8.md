# Carry-steered eight-digit tau recoding: prospective experiment

The existing four-step atlas deterministically picks two tau-digit patterns
for each eight-step block. A cold two-digit pair then costs two online mixed
additions if its orbit is absent from the 2,048-entry hot point table. That
pair is only one representative of its residue modulo `tau^8`. This
experiment uses a second valid pair in the **same residue class** when it
can be evaluated with one addition. The different pair changes the carry
into the next block; it does not change the scalar.

In tau coordinates, let `C0=(a0,b0)` and `C1=(a1,b1)` be the two four-step
pattern corrections. Their combined eight-step correction is

`C=(a0-18*a1-27*b1, b0+9*a1+9*b1)`.

For current coefficients `(a,b)`, any selected pair with
`C=(a,b) mod 81` has an integral next state

`q=((-2*(a-Ca)-3*(b-Cb))/81, ((a-Ca)+(b-Cb))/81)`.

Thus `(a,b)=C+tau^8*q` exactly. The map generator enumerates all 29,593
internally valid pairs, groups them by the 6,561 residues `(a mod 81,
b mod 81)`, and selects the pair minimizing, in order, predicted
additions (zero, one, or two), correction-coordinate L1, and pair index.
It stores a 16-bit pair index only when the best cost is below two;
otherwise it stores `65535`. This makes a 13,122-byte read-only map.
The generated map and each selected pair are checked for validity and
residue preservation.

At runtime, first compute the ordinary canonical pair. If it is already
zero/one-addition, keep it. Only for a cold two-digit pair, consult the
new residue map and substitute its valid one-addition pair when present.
Then use the exact quotient above as the carry and continue. The selected
pair is evaluated by the existing hot-orbit point table or positional
one-digit path. If the redundant expansion exceeds the prepared block
span, fall back to the existing exact positional scalar evaluator.
Prepared point entries and their setup are unchanged. The new static map,
lookup, quotient arithmetic, and any fallback belong to the online
interval. The format is variable-time and limited to public research
scalars.

This is a redundant tau-adic expansion. Pair validity is enforced within
each eight-step block; adjacent blocks need not jointly satisfy the
canonical width-four non-adjacent rule. The group identity above, not a
global NAF claim, establishes correctness. Redundant tau-adic digit
sets and symmetric digit sets are established prior art:

- https://eprint.iacr.org/2008/153
- https://eprint.iacr.org/2013/705

This experiment tests a bounded hot-table and residue-aware carry choice;
academic novelty remains unestablished.

## Freeze before new evaluation inputs

The generator, exact selection rule, fallback, and operation gate must be
committed and opened as a draft PR before generating evaluation scalar
files. The fresh workload uses 4,096 exactly uniform subgroup scalars per
case from SplitMix64 initial state
`20270417 ^ (curve_index << 32) ^ point_index`. It has the same two
registered subgroups and generator/`37P` points as the earlier panels.
Independent generic multiplication supplies the frozen output digests.
Compare `fused-hot-batch128` and
`fused-hot-steer-batch128` on identical inputs, alternating order.

The prospective operation gate requires all 16,384 steered outputs to
match generic multiplication; at least 3% fewer executed mixed additions
in **each** case; identical per-point prepared bytes and setup operations;
and an explicitly reported 13,122-byte static map. Preserve all raw
failures and span fallbacks. CPU wall speed and rho impact require five
paired AB/BA repetitions on a qualifying isolated physical host,
including recoding, map access, and any target-dependent setup.

## Exploratory feasibility screen

A separate 5,000-scalar-per-law screen with seed base `20270301` showed
5.50%–11.29% fewer predicted additions across the four subgroup/eigenvalue
laws. The smallest subgroup had zero span fallbacks in either arm. On one
56-bit root, span fallbacks fell from 503 to 493 per 5,000 scalars; the
other root had none. These are model diagnostics that helped set the gate,
not candidate evaluation results. Exact counts and source hashes are in
`carry-steer-screen.json`.
