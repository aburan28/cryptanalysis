# Pair adjacent τ steps across an empty digit position

## Frozen hypothesis and algebra

The scored two-neighbor free-gauge scalar evaluator runs one Jacobian
τ map at every descending digit position. Whenever the current position
has no addition, its τ step and the following step can share the
existing optimized tripling core. The following position may contain
one or two digits and may select a different gauge. This opt-in mode
uses exactly the same scalar reduction, digit streams, pair choice,
prepared points, mixed additions, and output policy as
`paired2-free-gauge-scored`.

For `psi(x,y)=(beta*x,y)`, `tau=1-psi` and
`tau^2=-3*psi`. The existing Jacobian tripling formula computes the
same output `X,Y` as two τ applications. If the second step changes
the free gauge by `delta` in `{0,1,2}`, scaling the tripling output
`Z` by `-beta^(delta+1)` represents the exact result. This costs one
field multiplication for `delta=0,1`; for `delta=2` the scale is `-1`
and costs a field subtraction. The current formulas count two ordinary
τ steps as `8M+4S`, and one paired step as `7M+4S` or `6M+4S`.
`tau_pairs + tau_pair_cheap_z` therefore counts the field
multiplications removed by the formula on nonidentity points. This
operation count does not predict CPU time by itself.

The fixed gate requires each candidate output to match an independent
affine oracle. It also requires identical recode, pair score, τ-step,
point-add, rotation, gauge, preparation, and inversion counters between
the control and paired mode. Only `tau_pairs` and
`tau_pair_cheap_z` may differ. The two counters must satisfy
`0 <= tau_pair_cheap_z <= tau_pairs <= tau_steps/2`.

## Held-out gate

Commit source, tests, this protocol, the affine fixture generator, and
the serial checker before generating fresh 1,024-pair fixtures on
`glv-j0-32` and `j0-56`. Freeze fixture bytes, seeds, and affine
output digests in a second commit before running either arm. Execute
control, paired, paired, control serially for each curve under Release
and UBSan. Preserve raw exit status, stdout, stderr, source and binary
hashes, exact operation counters, and correctness digests, including
all failures. The local host has no verified exclusive CPU or NUMA
partition: set `cpu_speedup_claim: null` and
`isolation_receipt: null`, regardless of local timing.

This is a batch scalar-stage diagnostic. A verified one-target result
and host-level isolation receipt are separate gates for an online CPU
speedup claim. Tripling and the identity `tau^2=-3*psi` follow from
the Xu–Yu–Han–Lu τ construction; academic novelty of this evaluator
combination has not been established.
