# Nine-seed chain lower bound in the current operation model

`seed_chain_bound.py` symbolically checks the nine width-four seed
coefficients and the exact dataflow in `src/main.rs::prepare`.  This is a
retrospective, algebraic screen on the existing seed table; it uses no new
scalar fixtures or CPU timings.  Run it with ordinary Python:

```sh
python3 experiments/prime-j0-secp256k1-native/seed_chain_bound.py
```

Represent points by coefficients in `Z[τ]`, with `τ²=3τ−3`.  The norm is
`N(a+bτ)=a²+3ab+3b²`.  Sign and multiplication by `ω=1−τ` preserve norm.
Doubling multiplies norm by 4, and the τ map multiplies it by 3.  The nine
required seeds have distinct sign/ω orbits and norms
`1, 4, 16, 7, 28, 19, 76, 13, 7` in source order.

Four required orbits have norms `7, 7, 13, 19`.  An integer coefficient
cannot reach any of these by doubling or τ, because none of their norms is
divisible by 4 or 3.  Every required orbit must be created at least once,
so those four demand additions.  None of the other required norms is
divisible by 3; each of their four non-base orbits therefore costs at least
a doubling.  With the current source counts, the lower bound is
`4×11 + 4×7 = 72 M+S` before unit rotations.  The implemented chain uses
exactly four mixed additions and four doublings, attaining this bound.  It
also uses two unit rotations, for 74 units before the separate orbit table.

The lower bound permits arbitrary extra intermediate points: they cannot
remove the mandatory creation cost of any target orbit.  Its scope is the
current graph of **one-result** group operations at the stated source costs.
It does not cover a combined multi-output formula, co-Z arithmetic, a new
digit alphabet with different seeds, or a different field-operation model.
It is not a claim that the complete scalar algorithm is optimal, novel, or
faster on a CPU.  Those are the remaining research directions.
