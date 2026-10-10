# Q1420 source and descendant W24 six-summand circuit gate

The first comparison uses the already frozen Q1420 one-target workload
`eee7f6ee5f6b` and the equal-size W24 bases: each has 16,772,828 usable
points and 8,386,414 signed classes. The source prefix ends at mask
16,763,440; the descendant-native base includes all masks through
16,777,215. `CONFIG.json` pins the workload, base-selection, route, and
selected-mask-stream hashes. The same public point is transported through
the verified oriented degree-263 map. The known fixture scalar is excluded
from every PDP input.

The exact codomain has coefficients `[1,0,0,A,b_raw]`. The coordinate shift
`y_normalized = y_codomain + A` gives `y²+xy=x³+b`, where
`b=b_raw+A²`, and `alpha=b^(1/4)`. For a nonzero trace-zero W24 parameter
`w`, set `u=H(w)` and `z=1/w`. A descendant leaf is constrained by

```
w*z = 1
u*(x+alpha) = alpha
Tr(alpha*z) = 0
```

These equations encode `x=alpha*(1+1/u)`. The rational-lift criterion on the
normalized codomain is `Tr(x+b/x²)=Tr(alpha/w)=0`. The source specialization
uses `alpha=b=1`. Exact W24 selection and ascending leaf ordering are encoded
in the XCNF; an out-of-base SAT solution cannot be promoted by filtering it
afterward.

For either normalized curve, the pair relation is
`S3(a,c,d)=(ad+c(a+d))²+c(ad)+b=0`. Six raw leaf coordinates use the
balanced pair tree `01,23,45,(01)(23),((0123)(45))`. Every intermediate is
finite. The four target choices are the x coordinates of `Q+jT`, `j=0..3`,
for a certified rational order-four point `T`; they share the same `[4]`
projection. The source and codomain lift sets must agree under the verified
degree-263 map, irrespective of their torsion-shift ordering.

First produce the target lifts and six positive geometry controls per base
from public points and the precommitted control masks. Independently replay
both group laws, the isogeny transport, all leaf equations, and every S3
link. Reject changed x and reciprocal-witness bits in the Boolean evaluator.
Then build one native-XOR XCNF per policy for Q1420 query zero, with an
external 300-second and 4-GiB construction cap. Save formula hashes, source
hashes, variable/clause/XOR counts, RSS, and wall time. A formula is a
construction result, not an observed natural relation.

Only after both formulas and replay pass, a bounded one-thread CryptoMiniSat
pilot may use `--maxtime=120` with a 150-second external wall guard and 4-GiB
RSS cap, in source then descendant order. Record a valid model only after
independent point/sign/mask/group-sum replay. A capped attempt is
`BOUNDED_UNKNOWN`, with its search and exit evidence retained. Stage timing
on this host is exploratory until the CPU isolation contract is met. The
four-policy end-to-end comparison still requires relation yield, novel rank,
final matrix solve, target descent, and the paired same-point rho solve.
