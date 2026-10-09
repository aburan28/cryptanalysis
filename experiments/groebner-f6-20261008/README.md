# Separator-conditioned algebraic query prototype

The prototype exactly decides whether a Boolean polynomial system has a root
when its equation-support graph admits a small elimination width. It
canonicalizes repeated GF(2) monomials, builds one Boolean factor per original
equation, joins factors containing the next variable, existentially projects
that variable, and stores one witness bit per surviving boundary assignment.
Reversing these witnesses reconstructs a solution, which is checked against
the original equations. An empty projected table proves unsatisfiability.

If the largest joined bag has `w` variables, each step enumerates at most
`2^w` states. The implementation's greedy order and factor lookups give
`O(sum_i 2^w_i * b_i)` elementary checks, where `b_i` is the number of factors
in elimination bucket `i`; memory is bounded by the projected tables and
witness maps. This is a conditional width bound, with explicit `width-cap` and
`state-cap` statuses. Its current output is a Boolean decision and one
assignment, not a complete Gröbner basis. The identity behind each step is

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
offers no useful separator for those inputs. A next structural test is the
longer summation-polynomial chain, where consecutive links share intermediate
point coordinates; the cost bound must use its measured bag width and the
certificate size, not the chain diagram alone.
