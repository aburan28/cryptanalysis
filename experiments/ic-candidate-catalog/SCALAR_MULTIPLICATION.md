# Scalar multiplication policy for IC candidates

The exact curve record describes a mathematical instance. Its
`endomorphism.actions` inventory holds only subgroup actions whose map and
eigenvalue have evidence. An endomorphism-order conductor or a favorable
`j`-invariant alone does not certify an accelerated scalar multiplication.
The inventory is initially `not_enumerated` for the three registered curves;
this is an explicit unknown, not a statement that no action exists.

New IC candidates use `schema: "ic-candidate/2"` and embed a
`scalar_multiplication` object conforming to
[`scalar-multiplication.schema.json`](scalar-multiplication.schema.json).
The six archived `ic-candidate/1` manifests keep their original hashes and
names; the semantic gate rejects new `/1` files. Each `/2` policy lists every
executed scalar multiplication role. Use distinct roles such as
`relation_query`, `target_shift`, `relation_check`, `target_descent`, and
`recovery_check`; describe any additional role rather than silently inheriting
a library default. The policy is inside the canonical candidate hash, so a
change of scalar method or selection rule produces a different `IC1...h...`
identity without adding another segment to the readable name.

Each use declares its point kind, algorithm, recoding and window, scalar
decomposition reference, coordinate and field arithmetic, precomputation
scope and cache key, exact eligibility rule, fallback, implementation digest,
and timing behavior. `selection.curve_uid` and `selection.subgroup_order` must
match the candidate. GLV, GLS, τ-adic, and custom endomorphism methods need a
`verified` action on that exact curve, with a map, subgroup eigenvalue
`lambda mod r`, proof reference, and replay reference. An unproved action
remains a proposal and cannot power an `IC1` method. The validator checks
metadata and artifact presence; the referenced verifier must replay the
map and subgroup relation, including `psi(G) = [lambda]G`, before marking an
action verified. It does not infer this relation from the conductor.
Algorithm and decomposition references inside the candidate are stable logical
rule names or content digests, not filesystem paths. A claimed constant-time
method carries a `timing_evidence_sha256`; a digest records the evidence
identity but does not itself prove side-channel behavior.
Runtime dispatch requires a named generic fallback and must report the
backend actually selected. A fallback cannot silently activate a second
endomorphism method; that would need its own proved action and policy use.

For example, a baseline use can declare `method: double_and_add`,
`endomorphism_action_ref: null`, binary recoding, no precomputation, and an
explicit fixed-base `relation_query` role. An accelerated candidate would
replace that use with `method: tau_adic`, a verified action reference, its
decomposition and digit rules, window, table scope, and fallback. Both
policies must record source digests already present in the candidate's
`implementation.sources_sha256` map. JSON parameters contain integers and
strings, never floats.

An automorphism quotient used to reduce a rho walk's search space is a
different choice from scalar decomposition used to compute `[k]P`. Record
the walk quotient in the rho reference or relation collector, and the scalar
algorithm wherever a scalar multiplication occurs. The paired rho reference
must disclose its own scalar setup and jump/restart policy; it is not inherited
from the IC candidate.

Every run must state the **resolved** scalar backend for each role, including
an automatic Sage or hardware dispatch. Record table build, conversions,
transfers, and cache preparation in their actual setup or online phases.
Keep target-independent preparation outside the primary one-target online
interval; charge target-dependent table or scalar work to that target.
Compare full operations and paired online wall time under the existing
measurement and CPU isolation rules. A faster field operation or scalar
kernel alone does not establish a faster DLP. `timing_behavior` records the
declared side-channel behavior; a constant-time claim needs separate evidence.
