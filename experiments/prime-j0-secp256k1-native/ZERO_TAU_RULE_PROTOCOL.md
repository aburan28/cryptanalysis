# Zero-τ priority in a mixed-radix scalar chain

This is a cheaper recoder candidate for the same secp256k1 short
Eisenstein representative and original nine width-four τ digit orbits.
At a nonzero state `(a,b)`, take zero-digit division by 2 **only if**
both coefficients are even and `a` is not divisible by 3. Otherwise,
take the fixed-digit τ transition. In particular, when `a` is
divisible by 3, a τ step has a zero digit and gets priority over a
possible double. The rule needs no search graph or extra point table.
Reconstruct every action stream and recount its complete source cost.
Compare this path with the existing selective mixed-alphabet path per
scalar, with ties selecting selective.

The original 64-case fixture is retrospective design data. An eight-rule
screen selected this mathematically simple zero-τ priority rule, whose
complete selector cost was 86,405 `M+S` against 86,711 for the prior
greedy-or-selective selector. The largest raw design saving among the
screened rules was only 319, versus this rule's 306; do not promote the
design score as a fresh result. The width-four digits have maximum
Eisenstein norm 76. Outside norm 152, the τ transition strictly lowers
norm and doubling quarters it. Within norm 152, the closed 559-state
integer ball was exhaustively checked for termination and cycles.

Freeze this protocol, `screen_radix_policy.py`, `zero_tau_rule.py`,
`make_zero_tau_fixture.py`, and `validate_zero_tau_rule.py` in a commit
before generating `zero-tau-fixture.json`. Use the checked repository
Sage launcher and save `--runtime-info` first. The new deterministic
fixture has eight bases and 32 scalars per base, no overlap with the six
prior local scalar fixtures, and a separate cross-check against the
exact-radix fixture from its sibling branch. Retain every case and
failure. The prospective source gate requires a lower aggregate
selector cost than the earlier greedy-or-selective selector on those
same new inputs, with group replay of every selected output.

If the source gate passes, implement this rule in the native evaluator
and check each ordered action stream, prepared seed, operation recount,
and public point. Its paired complete-operation comparator is the
earlier greedy-or-selective evaluator on the identical fresh inputs.
Both timed intervals include input decoding, both relevant recoders,
choice, preparation, evaluation, affine conversion, formatting, and
expected-point verification. A CPU speedup requires physical-host
isolation under `docs/ISOLATED_BENCHMARKS.md`; structural checks and
ordinary-host runs are not timing evidence.

This is a variable-time research candidate. Mixed-radix and
endomorphism scalar chains have prior art; academic novelty is
unproved.
