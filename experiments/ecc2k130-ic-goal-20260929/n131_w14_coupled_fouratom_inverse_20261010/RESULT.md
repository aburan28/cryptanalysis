# Degree-eight inverse for a same-seed four-atom partial sum

An exact resultant and a linearized product-space polynomial turn a proposed
four-atom output into an 8,192-state scan on the frozen N131 `W14` source.
The native scan completed in 7.496 s for the constructed output and 9.722 s
for an independently selected trace-zero control, with peak process RSS below
2 MiB. It recovered both source pair products in the positive case and no
algebraic hits in the control. Independent Sage replay verified the resultant,
four source points, projected subgroup point, reported roots, and sampled
rejections. The timings are diagnostics from an unisolated host.

## Construction and exact filter

Work on `y^2 + xy = x^3 + 1` over the polynomial-basis binary fields
specified in [`inputs.json`](inputs.json). Write `w=1/x(P)` for a diagonal
atom and fix one nonzero seed `s` in the source subspace `W_d`. Two atoms
whose source coordinates are `w` and `w+s` have product

`p = w(w+s) = w^2 + sw`.

The image `V_s={w^2+sw : w in W_d}` is an `F_2`-linear subspace of dimension
`d-1`, because the map has kernel `{0,s}`. Its linearized vanishing
polynomial `S_s(X)` has degree `2^(d-1)` but only `d` nonzero coefficient
positions. For two such pairs, let `p,q` be their source products, `C,D`
their reciprocal output coordinates, and `z` the reciprocal coordinate of
the four-atom sum. The following equations hold for every defined sum:

```text
g_p(C) = (1+p^2)C^2 + pC + s^2 = 0
g_q(D) = (1+q^2)D^2 + qD + s^2 = 0
U(C,D,z) = (1+C^2D^2)z^2 + CDz + (C+D)^2 = 0
```

Eliminating `C,D` gives
`H(s,p,q,z)=Res_C(g_p(C),Res_D(g_q(D),U(C,D,z)))`. Its binary-field
expression has 150 monomials and degree at most eight in each of `p`, `q`,
and `z`. For a proposed `z`, scan each `p in V_s` and compute
`gcd_Q(H(s,p,Q,z),S_s(Q))`. A positive-degree GCD proposes a `q in V_s`;
zero GCD degree rejects that entire product family. The native implementation
reduces the linearized polynomial modulo the degree-eight specialization of
`H` before computing the GCD, so it never materializes a dense degree-8192
polynomial during the scan. Every four-atom witness satisfying the equations
survives this filter. An algebraic hit still needs field-branch, actual
source-point, sign, folded-column, and group-sum replay before it can enter
a relation matrix.

## Frozen experiment

[`protocol.json`](protocol.json) and [`native_protocol.json`](native_protocol.json)
fix source hashes, input order, one worker, and 4 GiB RSS caps before their
respective runs. N41 uses `W6`, `s=t`, and the masks `2,3,6,7`. N131 uses
`W14`, `s=t`, and masks `18,19,24,25`. In both fields the positive reciprocal
output comes from four distinct folded columns. The separate control is a
trace-zero field element selected without constructing it from those four
points. These cases test exact inversion and rejection at one proposed
output apiece; they do not estimate the hit rate for ordinary public-target
queries. The complete IC candidate ID remains `null` because this is a
partial-sum oracle without target-conditioned output generation.

| Field | Case | Product states checked | Algebraic hits `(p,q)` | Native query s | Parent wall s | Peak process RSS bytes |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| `2^41` | constructed output | 32 / 32 | `(24,72)`, `(72,24)` | 0.000881 | 0.523 | 1,523,712 |
| `2^41` | trace-zero control | 32 / 32 | none | 0.000882 | 0.067 | 1,523,712 |
| `2^131` | constructed output | 8192 / 8192 | `(1112,1376)`, `(1376,1112)` | 7.496 | 7.509 | 1,966,080 |
| `2^131` | trace-zero control | 8192 / 8192 | none | 9.722 | 9.762 | 1,884,160 |

The original checked-Sage N131 scan reached 512 / 8192 states at its 120 s
cap and is preserved as [`result_n131_positive.json`](result_n131_positive.json)
with `CENSORED_TIME`. Both complete N41 Sage controls preceded the native
N131 runs. Native raw results and parent receipts are in the four
`native_run_*` directories. [`sage_audit.json`](sage_audit.json) records the
independent replay and source digests. The checked local Sage runtime is
recorded in [`sage_runtime_info.json`](sage_runtime_info.json).

## Next target-conditioned gate

The inverse accepts a *proposed* four-atom output; it does not generate
outputs constrained by the frozen public point. The next experiment should
derive a joint equation between that public point and two or more partial
sums, generate candidate `z` values from the joint constraint, and apply
this inverse before enumerating pair witnesses. Freeze an unpinned N41 public
point and a trace-zero control first. Record candidate-output count, oracle
calls, field-branch and group replays, ordinary verified relations, novel
rank, complete wall/RSS, and misses under the cap. Promote to the frozen
N131 public point only after the N41 gate has an independently replayed
ordinary relation. The N131 objective retains its one-worker, 600 s, 4 GiB
bound; the local scan times above are only one component of that budget.
