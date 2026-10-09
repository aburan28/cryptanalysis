# Separator-conditioned algebraic query prototype

The prototype exactly decides whether a Boolean polynomial system has a root
when its equation-support graph admits a small elimination width. It
canonicalizes repeated GF(2) monomials, builds one Boolean factor per original
equation, joins factors containing the next variable, existentially projects
that variable, and stores one witness bit per surviving boundary assignment.
Reversing these witnesses reconstructs a solution, which is checked against
the original equations. An empty projected table proves unsatisfiability.

If the largest joined bag has `w` variables, each step enumerates at most
`2^w` states. Factor construction first enumerates `2^s_e` assignments for
each equation scope `s_e`; elimination then enumerates `2^w_i` assignments
for each joined bag. The implementation charges both to one `state-cap`,
including a pre-allocation check for every factor table. A direct operation
bound is `O(sum_e 2^s_e |T_e| + sum_i 2^w_i b_i w_i + polynomial order
selection)`, where `|T_e|` is the number of monomials in equation `e` and
`b_i` is the number of factors joined in bucket `i`. Memory is bounded by
the factor tables and witness maps. This is a conditional width bound, with
explicit `width-cap` and `state-cap` statuses. Its current output is a
Boolean decision and one assignment. The identity behind each step is

`exists x: (F_1 and ... and F_k)`

on the joined scope, so the projection cannot add or lose satisfying boundary
assignments. The reverse witness map yields a full solution whenever the final
table is nonempty.

Chordal elimination already exploits low treewidth in polynomial ideals
([Cifuentes and Parrilo, 2016](https://arxiv.org/abs/1411.1745)). The research
direction here is to combine this exact separator condition with our
proof-carrying F4/F5 blocks: compute a local Macaulay projection only when its
boundary table is large, retain F5 signatures within blocks, and compose
certificates across separators. A new algorithmic bound would need to include
signature transport, certificate growth, and the width of the actual
point-decomposition equations. Greedy width itself is measured on each frozen
input; an equation spanning every variable is a direct counterexample to a
small-width route.

`test_separator.py` compares 245 random systems with exhaustive enumeration,
checks a 48-variable chain of quartic local equations at width four, and
exercises dense-width, cancellation, and state-cap cases. To inspect a frozen
query case, pass its panel JSON to `separator.py` with a recorded bag cap.

On the five frozen 12-variable, three-summand point-decomposition cases,
`separator.py --max-bag 8` reports `width-cap` with an equation touching all
12 Boolean variables in every case. The plain equation-support graph therefore
offers no useful separator for those inputs.

`chain_profile.py` expands each S3 auxiliary-coordinate link into exact GF(2)
equations, checks them on a curve-point decomposition, and computes induced
support width without allocating exponential factor tables. With field degree
`n=9`, subspace dimension `ell=3`, curve `b=1`, modulus `515`, and seed `1`:

| Summands | Boolean variables | Maximum equation support | Greedy induced width | Joined-state upper bound |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 18 | 15 | 15 | 72,702 |
| 4 | 30 | 21 | 21 | 4,265,982 |
| 5 | 42 | 21 | 21 | 8,459,262 |
| 6 | 54 | 21 | 21 | 12,652,542 |

The encoding keeps measured width at 21 as more S3 links are added for this
fixed field and subspace. Its middle equations already span 21 variables, so
the explicit-table prototype stops at its default cap of 12. A packed
truth-table or local proof-carrying F4 kernel is the next experiment at that
boundary. These seeded decompositions verify the equation encoding; they do
not estimate ordinary-query relation yield. Certificate growth and signature
transport across links remain the proof obligations for the hybrid proposal.
