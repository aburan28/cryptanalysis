# Frozen implicit orbit-closed W24/m5 unknown-witness SAT gate

The exact W24 census gives 2,198,485,492 usable subgroup points after
closing the source factor base under its 131-element Frobenius action, while
keeping 8,391,166 sign-Frobenius columns. This is a different factor-base
policy from the original W24/m6 base. Its formal five-summand support count
is large, but no natural PDP solver has been verified. The parent
[normal-basis gate](../ecc2k130-w24-normal-barrel-20261006/RESULT.md)
verified its exponent circuit only on supplied seeds and exponents. This
experiment asks whether a bounded CryptoMiniSat search can recover a
**hidden** five-summand group witness with both 24-bit seed masks and
Frobenius exponents unknown.

`CONFIG.json` freezes the parent result hashes, full factor-base count,
solver binary/version/hash, bounds, and the first five archived source group
controls. Interpret each archived `orbit_x` as the quotient word `w`, set
`u=H(w)` and curve `x=1+u⁻¹`, then choose the curve lift with smaller encoded
`y`. Add the five raw points in order and set `Q=[4]sum`. These
rules fix the planted input before its coordinates or SAT formula are
generated. If a selected point or S3 chain is exceptional for the current
encoding, preserve that outcome; do not replace a control.

The Boolean encoding has five leaves. Each leaf has a nonzero 24-bit W24
seed mask and an eight-bit Frobenius exponent constrained *inside the
formula* to `0..130`. Compose the archived full polynomial-to-normal map
with half-traces of the 24 W24 basis words, then use the verified eight
conditional 131-bit rotations to form `u = Frob^k(H(w))`. Convert `u` to
polynomial basis. Set `w=u²+u`, require an inverse witness `w*v=1` and
`Tr(v)=0` to enforce the source rationality law. Link the five leaves to
one of the four cofactor preimages of `Q` with four cleared S3 equations
and three free intermediate field values. The formula must not pin masks,
exponents, intermediate values or target-fiber selectors. A separately
constructed known assignment may diagnose a timeout, but cannot count as a
solver recovery.

Use the pinned CryptoMiniSat binary, one worker, seed zero, 100,000 conflict
limit, external 30-second planted wall bound and 4-GiB observed RSS bound.
Cap formula construction at 300 seconds and 4 GiB. Preserve an XCNF hash,
all clauses/XOR rows, raw stdout/stderr, exit, timeout/OOM state, phases,
and any model. Independently replay a returned model as curve points,
verify `[4]sum=Q`, and check all five seed/exponent memberships and the
four S3 links. A model failing replay is not a success. If no independently
verified unknown witness is found, retain the failure and do **not** run
the ordinary target.

After a verified planted model, run exactly one ordinary target from the
frozen workload `eee7f6ee5f6b` with its unchanged public point. Its solver
gets 2,000,000 conflicts and 600 seconds. Record attempts, verified
decompositions, relation novelty, and all target-dependent costs; do not
claim an IC online speedup without the remaining factor-log preparation,
final relation matrix, target recovery and same-point rho stages. The
host is unisolated, so CPU timing ratios remain exploratory.

Copy the bounded Boolean field/group arithmetic from the original W24/m6
SAT control with pinned source hashes, retaining its independent Sage and
group-replay checks. The exact source code, build commands, Sage runtime
receipt, input/result hashes, and all failures must enter this PR. Run all
new local Sage jobs through `/Volumes/SSD990/cryptanalysis/sage` and save
`--runtime-info` before starting them. This proposal keeps
`candidate_id: null` until a complete IC method is manifest and measured.
