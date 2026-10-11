# A reusable annihilator and its dimension limit

This is a local algebraic derivation for a specific polynomial basis. It is
not a claimed new Gröbner algorithm, novelty result, degree-of-regularity
bound or end-to-end asymptotic improvement.

Let the characteristic be two, let beta_i=z^i for 0<=i<ell, assume ell>=3,
and require 3ell-4<n so that the following polynomials do not reduce modulo
the degree-n field polynomial. Define

Gamma_ij = beta_i^2 beta_j + beta_i beta_j^2
         = z^(2i+j) + z^(i+2j),  i<j.

The binary rank of these quadratic coefficient columns is **3ell-6**.

## Proof

Treat each column as an edge-incidence vector on vertices 1 through 3ell-4.
Its endpoints 2i+j and i+2j have opposite residues modulo three. Therefore
each edge stays within either the positive multiples of three or their
complement. There are no edges between these two sets.

For ell=3, vertices 1,2,4,5 form one connected component via edges
(1,2),(2,4),(4,5), and vertex3 is the other component. Assume the two sets
are connected for ell=L>=3. Increasing to ell=L+1 adds vertices
3L-3, 3L-2 and 3L-1. The new pairs with j=L and respectively
i=L-3, L-2 and L-1 supply edges

- (3L-6, 3L-3), joining the new multiple of three to its old component;
- (3L-4, 3L-2), joining the first other vertex to its old component;
- (3L-2, 3L-1), joining the final vertex to that component.

All earlier edges remain, so there are exactly two components for every
ell>=3. The incidence vectors of a connected graph over F2 span precisely
the vectors of even parity on that component: a spanning tree provides
|V|-1 independent vectors, and the parity condition is one upper bound.
Thus the total rank is (3ell-4)-2=3ell-6.

Coordinate zero and coordinates above 3ell-4 never occur. A complete basis
of the annihilator therefore consists of coordinate zero, parity on each
of the two components, and each unused high coordinate. Its dimension is
**n-3ell+6**.

## Exact transport and guarded applicability

Suppose the observed quadratic columns are alpha*Gamma_ij for nonzero
alpha in the declared field. Multiplication by alpha is an invertible
binary linear map M_alpha. If A annihilates Gamma, then
W = A M_(alpha^-1) annihilates the observed columns and carries explicit
original-equation combination witnesses. Its rank is unchanged.

This is an exact row transformation. It does not justify using A directly
on unnormalized columns. Every implementation must verify alpha*alpha^-1=1,
check all observed quadratic columns against alpha*Gamma, preserve the
original-row witnesses, and use exact fallback for zero alpha or mismatch.
The finite controls include cases where omitting transport fails, as well
as a polynomial-reduction counterexample outside the support condition.

For a residual with n equation coordinates and ell Boolean variables,
constant combinations that remove the quadratic terms span at most
n-3ell+6 affine equations. Consequently, a unique solution obtained from
this affine subsystem alone requires **n+6>=4ell**. This is necessary,
not sufficient. Inconsistency can still yield a direct certificate at
lower rank.

At n=31 the quadratic ranks for ell7,8,9,10,11 are 15,18,21,24,27,
and the corresponding annihilator dimensions are 16,13,10,7,4. In
particular, the unique-affine-assignment fast path cannot generally extend
to ell10 by this construction alone: seven independent constraints cannot
uniquely determine ten variables.

## Next bounded algorithm experiment

First measure a guarded normalized affine constructor, including field
inversion, all quadratic-column checks, coefficient transforms and proof
transport. Compare identical complete-query inputs against both round40
and the widened GPU path. Do not infer wall-time gains from the rank lemma.

For deficient affine rank r, a separate certificate format could retain
original-equation witnesses for the r independent affine consequences.
An independent checker can verify those identities, solve the affine
subsystem and exhaust its 2^(ell-r) remaining assignments against the
original residual equations. Every original root lies in that affine
subspace, so this bounded enumeration proves completeness. It must retain
all roots, represent inconsistent affine systems correctly, and preserve
the old exhaustive fallback when rank is too small or a budget is exceeded.
This is a proposed extension, not implemented solver behavior.

If n is roughly 3ell, the proved annihilator dimension is bounded rather
than proportional to ell. That limitation prevents treating this lemma
as evidence of an asymptotic improvement for the whole growing family.

## Relation to the literature

[Polynomial XL](https://arxiv.org/abs/2112.05023) already studies eliminating
Macaulay columns over a polynomial ring before fixing variables. It is
relevant prior work for reusable symbolic elimination; its heuristic
complexity analysis does not prove a bound for this guarded constructor.

[Notes on summation polynomials](https://arxiv.org/abs/1503.08001) gives
examples where low-degree consequences make first-fall-degree reasoning
misleading as a predictor of the degree of regularity. This is why the
rank lemma is being used as an applicability and operation-count result,
with complete query measurements and counterexamples still required.

The rank proof above is our explicit derivation; the cited papers are
context, not an attribution of this particular lemma or a novelty search.
