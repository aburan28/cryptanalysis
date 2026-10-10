# A symmetric quotient for same-seed four-atom decomposition

The four-atom resultant has an exact **87-term symmetric representation**
in the aggregate pair product sum `P=p+q` and product `T=pq`, down from
150 terms in the ordered products `p,q`. For distinct source pairs, the
representation halves the algebraic state domain: one fixed N131 `W14`
seed has **33,550,336 unordered product keys** instead of 67,100,672
ordered distinct `(p,q)` keys. A further exact constraint places `T` in
an `F_2`-linear image of size 4,096 once a nonzero `P` is fixed. These
identities preserve every valid same-seed four-atom witness and provide a
smaller state for a target-coupled solver.

## Identity and conditional domain

For a nonzero source seed `s`, let `V_s={w²+sw : w in W_d}`. It has
dimension `d-1`, with `2^(d-1)` elements. If the two source-pair products
are `p,q in V_s`, set `P=p+q` and `T=pq`. In characteristic two, the
power sums `S_k=p^k+q^k` satisfy `S_0=0`, `S_1=P`, and
`S_k=P*S_(k-1)+T*S_(k-2)`. Replacing every swapped monomial orbit of the
archived `H(s,p,q,z)` by this recurrence gives `Hbar(s,P,T,z)`.
Checked Sage proved the **polynomial identity**
`H(s,p,q,z)=Hbar(s,p+q,pq,z)` over `F_2[s,p,q,z]`; `Hbar` has 87 terms
and degree bounds `(16,8,8,8)` in `(s,P,T,z)`.

For fixed `P in V_s`, `q=p+P` and therefore `T=p²+Pp`. The map
`L_P: V_s -> F_(2^n)`, `p -> p²+Pp`, is linear over `F_2`. Its kernel is
`{0,P}` when `P!=0`, so its image has `2^(d-2)` elements; at `P=0`,
squaring is injective and the image has `2^(d-1)` elements. In this
same-seed construction `P=0` repeats the source pair, so distinct
four-atom witnesses require `P!=0`. Hence there are exactly
`(2^(d-1)-1)*2^(d-2)` algebraic quotient keys per fixed seed before
source-point validity, signs, or folded-column exclusions.

## Frozen checks

The [protocol](protocol.json) hashes the [Sage checker](run.py), archived
[resultant](../n131_w14_coupled_fouratom_inverse_20261010/resultant_terms.json),
and [control inputs](../n131_w14_coupled_fouratom_inverse_20261010/inputs.json)
before execution. The [runtime receipt](sage_runtime_info.json) records
the checked local Sage build. The [result](result.json) includes the exact
polynomial identity, 256 N41 and 128 N131 sampled field evaluations,
conditional image sizes, and the frozen constructed and trace-zero controls.
The [receipt audit](audit.json) compares all four controls to archived
native inverse results.

| Fixed seed | Product space `|V_s|` | Nonzero-`P` image size | Ordered distinct keys | Quotient keys | Constructed-output algebraic hits |
| --- | ---: | ---: | ---: | ---: | ---: |
| N41 `W6`, `s=t` | 32 | 16 | 992 | 496 | 2 ordered / 1 quotient |
| N131 `W14`, `s=t` | 8,192 | 4,096 | 67,100,672 | 33,550,336 | constructed quotient key `(312,1352960)` survives |

The N41 trace-zero control has zero hits in both representations. For N131,
the constructed quotient key vanishes at the constructed output and does
not vanish at the frozen trace-zero control; the archived complete native
inverse found two ordered constructed hits and zero control hits.
These are exact algebraic and correctness checks. The N41 and N131 Sage
panel intervals in `result.json` are exploratory diagnostics on an
unisolated host, not a paired online speed measurement.

The [first setup attempt](setup_failure.json) stopped before algebraic
checks because that Sage field class lacks `fetch_int`; the final source
decodes the frozen polynomial-basis integers from coefficient bits.

## Target-coupled next gate

The quotient removes the order symmetry and reduces the conditional
finite domain, but a proposed four-atom output `z` is still required.
For N131, the 8,191 nonzero `P` values per seed still require an output
membership calculation without further target pruning. The next solver
experiment should encode `(s,P,T)` for each constrained four-atom block,
enforce `P in V_s` and `T in L_P(V_s)`, and propagate these domains through
the public-target S3 joins while several blocks are free. The first gate
is the frozen N41 output-fixed positive control and unpinned public point:
record how many complete quotient families the target eliminates before
enumeration, then replay a verified twelve-point relation. A source-bound
N131 resource projection must precede any 600-second public-point query.
This stage has `candidate_id: null` because it is a partial-sum constraint,
not a complete IC pipeline.
