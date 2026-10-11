# Degree-eight target-conditioned eliminant for two fixed-seed pair domains

Two free fixed-seed pair outputs can be eliminated exactly from one N131 S3
link. The resulting **single `GF(2^131)` equation** depends only on their two
17-bit source selectors and the proposed block-output reciprocal coordinate.
For fixed source selectors it is a polynomial of degree at most eight in that
output. On four independently replayed four-point blocks from the archived
16-point relation, it has degree eight with **eight distinct exact roots** in
each block. A frozen 4-positive/128-negative field panel and an independent
field implementation agree with enumeration of both roots of each source-pair
quadratic. The direct Boolean encoding of one eliminant passes all **176,063**
of its CNF and native-XOR records on a complete control assignment.

## Elimination and exactness

Work over `GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, curve ID
`EC1N131Ckb1heb5f1998f20b`. The two free outputs `a,b` use the audited W18
fixed seed `212` and the corresponding pair rotations from the
[16-summand source](../n131_fixed_seed_eight_pair_circuit_20261010/RESULT.md).
Their exact pair equations are

`F(a)=k a²+p a+t=0` and `G(b)=ell b²+q b+u=0`,

where `p,q` are binary-linear images of the 17-bit selectors. The constants
`t,u` are the Frobenius-rotated square of the seed halftrace, and
`k=1+t`, `ell=1+u`. Both are nonzero: a zero `k` would force the nonzero
seed to equal zero under the Artin–Schreier identity. Set

`alpha=p/k`, `beta=t/k`, `gamma=q/ell`, `delta=u/ell`.

Reducing the standard reciprocal S3 equation
`(abc)²+abc+(a+b+c)²=0` by `a²=alpha*a+beta` and
`b²=gamma*b+delta` gives `Aab+Ba+Cb+D=0`, with

```text
A = c² alpha gamma + c
B = c² alpha delta + alpha
C = c² beta gamma + gamma
D = c² beta delta + beta + delta + c².
```

Write `M=Aa+C` and `N=Ba+D`. Eliminating `b` from `Mb+N=0` and `G(b)=0`
gives `ell*N²+q*N*M+u*M²=0`. Its coefficients in `a²,a,1` are

```text
L2 = ell B² + q B A + u A²
L1 = q (B C + D A)
L0 = ell D² + q D C + u C².
```

After reducing `a²`, put `R=L2*alpha+L1` and `S=L2*beta+L0`.
The exact two-pair eliminant is

`E(p,q,c)=k S²+p S R+t R²=0`.

For source selectors whose pair quadratics have field roots, `E=0` is
equivalent to the existence of pair-output coordinates `a,b` satisfying
both pair equations and S3. If `R != 0`, the linear remainder fixes
`a=S/R`; if `R=0`, `E=0` forces `S=0`. Likewise the clearing step for `b`
handles `M=0`: when both `M` and `N` vanish, either field root of the valid
source pair is available. Every coefficient is polynomial in `c` of degree
at most two before the final resultant, so `E` has degree at most eight.
The [producer](run.py) computes both field-value and polynomial forms.

## Frozen N131 controls and size gate

The [protocol](protocol.json) freezes the curve, eight archived source-mask
pairs, four constructed block outputs, source hashes, 32 one-bit perturbations
per output, one worker, a 120-second component cap, and 4 GiB RSS. The
[result](result.json) checked all four positive block outputs and rejected
all **128** perturbations; for each coordinate, eliminant membership matched
an explicit check of the four combinations of the two pair roots. Each
positive degree-eight polynomial had eight distinct roots, including its
constructed group output. The separate [independent audit](audit_result.json)
uses a different field multiplier and square/reduction path from the
[earlier verified N131 field implementation](../n131_fixed_seed_halftrace_cubic_20261011/verify.py).

| One two-pair block, excluding the shared source BDD | Existing pair equations plus S3 | Direct eliminant circuit |
| --- | ---: | ---: |
| AND gates | 16,088 | **50,780** |
| Boolean variables | 25,198 | **74,537** |
| CNF clauses | 48,658 | **152,471** |
| Native-XOR rows | 8,682 | **23,592** |

The [matched local-circuit receipt](baseline_gate_result.json) rebuilds the
two rotated source-pair equations and their S3 link, and checks their complete
control assignment. Both columns exclude the same shared source BDD.

The new symbolic dependency goes directly from 34 source-selector bits and
the block output to a field equation. Its direct Boolean circuit is about
3.16 times larger in AND gates than the local equations it replaces, so
formula size alone does not justify inserting it into the full N131 SAT
query. The existing [native fixed-seed hash join](../n131_w18_seedwise_hashjoin_20261011/RESULT.md)
already checks a supplied four-point output efficiently. The useful next
gate is **partial target-conditioned propagation**: with one or both pair
selectors still free and only some block-output bits constrained by the
public point, determine whether this eliminant rejects whole selector
families earlier than the original S3 circuit. Freeze the same source,
partial-output laws, resource cap, and complete-relation control before a
solver comparison. Promote it into an ordinary N131 relation worker only if
that gate produces new useful pruning under the full 600-second/4-GiB
envelope.

This is a component method with `candidate_id: null`. Relation yield, useful
rank, factor logs, and single-target online accounting remain downstream of
an independently verified ordinary decomposition. Reproduce the frozen
component with `python3.12 -B run.py freeze`, `python3.12 -B run.py run`,
`python3.12 -B verify.py`, and `python3.12 -B baseline_gate.py` from a fresh
copy of this write-once directory.
