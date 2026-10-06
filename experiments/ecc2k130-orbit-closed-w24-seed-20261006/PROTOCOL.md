# Implicit orbit-closed W24 seed gate

The merged [exact W24 orbit census](../ecc2k130-263-w24-orbit-columns-20261005/RESULT.md)
shows that folding unchanged W24 saves only 2,066 potential columns. Closing
its signed subgroup points under all 131 source Frobenius powers instead
defines 2,198,485,492 geometric points in 8,391,166 orbits. This policy is
not a measured factor-base/PDP candidate: its membership and solver costs
are unknown. This gate tests the smallest reusable part of an implicit
representation, before spending resources on an m5 ordinary-query PDP.

The source field is `GF(2^131)` in polynomial basis with modulus
`t^131+t^13+t^2+t+1`; the source curve is
`EC1N131Ckb1h136f03e58c98`, `y²+xy=x³+1`, with subgroup order
`680564733841876926932320129493409985129`. A W24 seed is the nonzero
combination of `t^j+Tr(t^j)`, `j=1,...,24`. A positive encoded summand
uses `(mask,k)`, where `k` is a residue modulo 131 and its field coordinate
is the `2^k`-th power of the seed. Because the source curve is defined over
`F₂`, Frobenius commutes with the cofactor-four projection of its group
point. The verifier must check that statement on actual archived subgroup
points, not infer it from field membership alone.

`CONFIG.json` pins the first eight source controls in the independently
verified equal-size W24 workload and seven exponents
`0,1,2,7,31,65,130`, giving 56 positive field-coordinate controls. The
eight group controls use one exponent each by the published index rule.
The 64 negative field inputs come from the exact SHA-256 domain and input
law in the config. If one is a member, retain that result; do not replace
it. These are correctness controls and an operation-count panel, not
ordinary target decompositions or a natural-yield estimate. No held-out
target is selected or consumed here.

The producer will construct the 131 conjugate W24 bases using polynomial
GF(2) squaring, build a binary echelon for each, and return all exact
`(exponent,mask)` witnesses for each input. It must reconstruct every
witness and record the number of subspaces and XOR reductions tested. A
separate checked-Sage verifier will derive the original W24 basis from the
field, test all 131 Frobenius images using Sage field arithmetic and the
direct polynomial-mask rule, and replay the eight projected group controls
on the exact source curve. This avoids treating agreement between two calls
to the same echelon routine as independence.

Pass only if all 56 positives reconstruct, all eight group projections
match, and Sage independently agrees on all 120 field membership decisions
and witnesses. Preserve failures and resource exits. The primary output is
an exact membership/correctness record and deterministic work counts; any
wall time is an unisolated exploratory diagnostic. The 4-GiB/120-s producer
and 4-GiB/180-s Sage limits are stop rules. The checked repository Sage
launcher and its `--runtime-info` receipt are mandatory for that verifier.

This gate does not measure ordinary m5 PDP yield, useful rank, matrix work,
target descent, one-target DLP or rho. `candidate_id` and all end-to-end
costs remain `null`. A successful gate admits an ordinary-query PDP
formulation with seed and exponent variables to be preregistered separately;
it does not by itself select this policy over original W24/m6, W28/m5 or
the degree-263 descendant.
