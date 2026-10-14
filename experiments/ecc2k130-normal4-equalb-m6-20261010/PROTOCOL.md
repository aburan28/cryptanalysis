# Equal-B six-policy ECC2K-130 input gate

This protocol fixes a paired six-summand PDP comparison at
`B=11,743,888` actual subgroup-usable points on the exact source curve and
its oriented degree-263 descendant. It extends the [Q1420 four-policy input
gate](../ecc2k130-263-equal-w24-workload-20261005/RESULT.md) with the
[independently replayed Q1421 normal-weight-four base](../ecc2k130-normal-weight4-base-20261009/RESULT.md)
and its forward image. The one-target public point is the frozen Q1420
primary workload `eee7f6ee5f6b`. The new ordinary relation-query sequence
below is target-independent and has a separate identity. This input gate
has `candidate_id: null` until exact PDP, collection, LA and descent
policies are wired.

## Source identity and factor bases

[`CONFIG.json`](CONFIG.json) pins the Q1420 source/native base selection,
verified route manifest, primary target and exact mask archives, plus Q1421's
producer, independent Sage replay and run manifest, all by SHA-256. The field
is `GF(2^131)` with polynomial `t^131+t^13+t^2+t+1`. The source is
`EC1N131Ckb1h136f03e58c98`; the exact unnormalized codomain is
`EC1N131Cbinh833014327b07`. The route is
`IW1E263d1hadee4e69fa3d`, with inverse on the prime-order subgroup given
by the dual map followed by multiplication by `263^(-1) mod r`.

Q1421 has 5,871,944 signed classes and two subgroup points per class. For
each W24 seed geometry, select the **first 5,871,944 masks in increasing
integer order** from its complete verified gzip stream. Source W24 has
8,393,232 full signed classes, and descendant-native W24 has 8,386,414, so
both prefixes exist. Hash selected mask bytes as little-endian unsigned
32-bit words; save the last selected and first excluded masks. Do not choose
a different prefix after seeing group or solver outcomes. The normal4 base
uses every one of its 44,824 rational canonical orbits and all 131 rotations,
under Q1421's exact sign rule. This makes all six policies have the same
actual `B`:

| Policy | Curve | Base rule |
| --- | --- | --- |
| `w24_source` | source | Selected source W24 prefix, cofactor-four projected |
| `w24_transported` | codomain | Forward images of `w24_source` |
| `w24_descendant_native` | codomain | Selected native W24 prefix on the normalized model, inverse-shifted to the exact codomain |
| `w24_pullback` | source | Inverse-route images of `w24_descendant_native` |
| `normal4_source` | source | Complete Q1421 normal-weight-four base |
| `normal4_transported` | codomain | Forward images of `normal4_source` |

The three source/image pairs have identical group-sum hit vectors when
queries are transported through the same verified map. For normal4, the
source field Frobenius orbit quotient transports to a subgroup action
`tau = phi o pi o ([263^(-1) mod r] o dual)`. This defines an exact
44,824-column *potential* quotient on the transported subgroup. It does not
identify `tau` with coordinate Frobenius on the descendant model or assume a
low-cost native endomorphism there. Map evaluation and orbit-normalization
costs must be measured for the transported policy.

The full input producer must verify both gzip and decompressed-stream hashes,
full counts and monotone mask order before reporting either prefix. Freeze
64 control indices for each W24 seed prefix with SHA-256 of
`ecc2k130-normal4-equalb-m6-base-control-v1|<geometry>|<counter>` reduced
modulo 5,871,944, skipping repeated indices. The transported/pullback
policies inherit their seed indices. Use the 128 fixed Q1421 point sample for
normal4 source and forward images. An independent checked-Sage verifier must
reconstruct the route and normalized/native model, validate sampled points
and subgroup order, map and dual identities, and the target point on both
curves. Preserve failures and resource receipts. The two full W24 point sets
need not be stored as redundant multi-gigabyte encoded-point tables: the
verified ordered mask stream, field/curve construction, and ordered route
identify them exactly.

## Frozen ordinary queries and target accounting

For counter starting at zero, hash UTF-8
`ecc2k130-normal4-equalb-m6-ordinary-v1`, a zero byte, then the counter as
eight big-endian bytes with SHA-256. Interpret the first 17 digest bytes as
a big-endian integer, mask to 130 bits, and reject zero, values at least the
exact subgroup order, and duplicate accepted scalars. The accepted scalar
defines a source public query `[a]G`; its forward degree-263 image is the
paired codomain query. Solver inputs receive public points and policy IDs,
never these scalars. The scalars are fixture data for independent relation
replay and RHS construction. The first 16 accepted queries are the pilot,
the first 256 the yield screen, and the first 65,536 the rank trajectory;
these prefixes and this law are frozen before any PDP result. Hash the
accepted scalar stream by concatenating each scalar as exactly 17 big-endian
bytes, without counters or length prefixes; retain the accepted counters and
first 16 scalars in the producer receipt for direct replay.

The sole primary DLP target remains the one source/codomain public-point
pair in Q1420 `primary_workload.json`, with workload ID `eee7f6ee5f6b`.
The 511 other Q1420 corpus points remain dormant controls until the
single-target study is complete. Relation queries above are reusable
precomputation and do not depend on that target. Later target-dependent
operations begin the one-target online timer only after reusable base/index
work is ready; charge every target-dependent attempt, map evaluation,
descent, and recovery check to the target. Keep reusable preparation and
cold-start costs separately. A same-point automorphism-aware rho solve is
the paired online reference.

## Execution and advancement

Commit and open this protocol and input code before deriving the held-out
ordinary query points or inspecting PDP outcomes. The producer and its
independent verifier each have one worker, 1,800 seconds wall and 4 GiB RSS.
Save the checked `/Volumes/SSD990/cryptanalysis/sage --runtime-info`
receipt before new local Sage jobs, and launch them through that repository
launcher. Preserve a row for every timeout, OOM, failed source check and
rejected relation; local host timings remain diagnostic without a qualifying
CPU-isolation receipt.

The next PR must publish selected W24 prefix hashes, sampled point/map
replay, source and codomain ordinary-query point digests, fixture scalar
replay and the primary target binding. Then preregister exact six-summand
PDP implementations and limits against those inputs, including at least a
compact normal4 encoding and a matched W24 control. A planted relation is
an implementation control; ordinary-query verified yield, novel rank per
query, matrix and target costs decide advancement. At every stage retain
zero-yield cells and source/binary hashes. Promote an `IC1` candidate only
after all algorithm-affecting stages and exact base points are fixed.

Run the source-binding preflight before opening the protocol PR:

```sh
python3 experiments/ecc2k130-normal4-equalb-m6-20261010/preflight.py
python3 -m unittest discover -s experiments/ecc2k130-normal4-equalb-m6-20261010 -p 'test_*.py'
```
