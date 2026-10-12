# Native zero-τ rule replay and isolated timing handoff

Freeze `src/mixed_radix.rs`, the CLI dispatch in `src/main.rs`,
`make_zero_tau_action_fingerprints.py`,
`make_zero_tau_seed_fixture.py`, `run_zero_tau_native_checks.py`,
and this protocol before full native replay. An offline release compile
may precede the freeze to catch syntax errors, without executing the
fixture panel.

The native recoder must apply exactly the priority rule in
`ZERO_TAU_RULE_PROTOCOL.md`, including the original width-four digit
table and strict per-scalar comparison against selective recoding.
Check all 320 ordered action streams against Python's compact FNV-1a
fingerprints; these fingerprints are regression controls, while the
independent expected public points are the correctness certificates.
Check each short representative, prepared Sage seed, source count,
evaluator operation recount, public point, and exceptional cached-add
count. Retain all raw exits and failures in the receipt. Use untimed
single-case handoffs for both selector arms against the previous mixed
radix evaluator on the same inputs.

For isolated timing, pair `--benchmark-zero-tau-case` against
`--benchmark-mixed-radix-case` on each of the same 256 new scalar/base/
expected-output triples. Both timers start before scalar/base decoding
and include lattice reduction, both relevant recoders, the choice,
point preparation, evaluation, affine conversion, formatting, and
expected-point comparison. Charge the whole operation, including failed
attempts and raw failures. A CPU speedup requires the repository's
physical-host isolation preflight and noise gates. Structural manifest
validation and ordinary-host correctness replay do not qualify.

No constant-time or academic-novelty claim is made.
