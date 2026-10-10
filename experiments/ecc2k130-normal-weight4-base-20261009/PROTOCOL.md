# Exact normal-weight-four source factor-base gate for ECC2K-130

This protocol tests a Frobenius-stable base on the exact ECC2K-130 source
curve. Its field parameters are the normal-basis words of Hamming weight
exactly four, using the independently verified normal basis in the
[W24 barrel result](../ecc2k130-w24-normal-barrel-20261006/RESULT.md).
The set contains exactly `C(131,4)=11,716,640` nonzero parameters in
`89,440` full field-Frobenius orbits. Those are combinatorial input counts;
actual subgroup-usable points and matrix columns require the census below.
This is proposal `Q1421`, with `candidate_id: null`.

## Mathematical and input identity

[`CONFIG.json`](CONFIG.json) fixes polynomial field modulus
`t^131+t^13+t^2+t+1`, source curve
`EC1N131Ckb1h136f03e58c98`, its prime-order subgroup and cofactor-four
projection, the parent normal-basis result SHA-256, and every count rule.
The producer must independently check the parent's full 131-word
Frobenius orbit, inverse conversion matrices, normal-basis rank, and
`Tr(beta)=1`. A four-bit normal word has trace zero. For each parameter
`w`, the established source model gives rationality exactly when
`Tr(1/w)=0`; `w` and `1/w` are the only signed projection collision.
Frobenius rotates the 131 normal-coordinate bits and acts on source
subgroup points. It preserves both rationality and reciprocal membership.

Enumerate one representative of each four-subset under cyclic rotation.
Represent a four-subset by the four positive gaps between consecutive set
bits around the 131-cycle. Keep the lexicographically least of the four
cyclic gap rotations and set bits `0,a,a+b,a+b+c`. The complete positive
gap enumeration must produce 89,440 representatives, with every raw mask
in a length-131 orbit. The protocol does not select a favorable subset
after observing rationality.

## Exact census and accounting

For every canonical representative, form `w` by XOR of the four frozen
normal-basis polynomial words. Invert it in `GF(2^131)`, convert `1/w`
back to normal coordinates, and test the parity and weight of that
coordinate word. Parity zero selects a rational orbit. If its inverse has
weight four, record a reciprocal partner orbit. Every reciprocal partner
must itself be rational; the partner count must be even and inversion
must pair distinct field-Frobenius orbits. A self-reciprocal orbit would
make inversion an order-two action on an odd 131-cycle, forcing `w=1`;
that element has trace one and is outside this base. Let `R` be rational orbits and
`P` be rational orbits with an in-base reciprocal partner. Then report:

`C = 131*(R-P/2)` signed source classes,
`B = 2*C` actual nonidentity subgroup points before sign folding, and
`K = R-P/2` signed-Frobenius potential matrix columns.

Hash the canonical full and rational orbit-representative streams in
lexicographic gap order as little-endian 17-byte normal-coordinate masks;
record the parent, config, executable source, and receipt hashes. The
normal-form digest plus the frozen 131-rotation rule identifies the full
parameter set without writing a multi-gigabyte point table. Preserve
integer counts and raw failures, wall and CPU time, peak RSS, and exact
command and runtime receipts. One worker has 900 seconds and 4 GiB peak
RSS. Host wall time is a reproducibility diagnostic without a qualifying
CPU-isolation receipt.

An independently written checked-Sage verifier must reconstruct all
89,440 canonical gap representatives and every rationality/reciprocal
decision using Sage field arithmetic; it must not call the producer's
inversion or conversion code. It must match all counts and stream hashes.
Before the Sage job, save `/Volumes/SSD990/cryptanalysis/sage --runtime-info`;
launch the verifier only through that checked repository launcher. A
frozen SHA-256 sample of 128 rational orbits must also reconstruct the
source-curve points, verify cofactor-four projection, subgroup order,
and multiple Frobenius images. Independently verify the signed point identity
on the first 16 reciprocal partner orbits in canonical gap order (or all
partner orbits when fewer exist).
Mutation controls must reject a changed normal-basis word and a changed
rationality bit. An incomplete verifier or resource failure keeps the base
at proposal status.

## Decision boundary

Advance to a matched ordinary-query six-summand PDP test only if the
independent full census and sampled point controls pass, `B` reaches the
existing 4,121,293-point necessary 1% m6 support threshold, and `K` is at
most 83,843, one percent of the frozen W24 source quotient. Report the
formal unordered-multiset mean `C(B+5,6)/(r-1)` as a counting diagnostic,
not a natural relation yield. The resulting base will have a different
actual `B` from W24; any follow-on four-policy comparison must freeze
equal-`B` subsets and the same ordinary query law before measuring
verified relations, novel rank, matrix cost, target descent, and matched
rho. No solver, query, or target-dependent timing belongs to this census.

After this protocol and source are committed, run from the repository root
with fresh output paths:

```sh
python3 -m unittest discover -s experiments/ecc2k130-normal-weight4-base-20261009 -p test_census.py
python3 experiments/ecc2k130-normal-weight4-base-20261009/census.py \
  --out /tmp/ecc2k130-weight4-producer.json
/Volumes/SSD990/cryptanalysis/sage --runtime-info \
  > /tmp/ecc2k130-weight4-runtime.json
/Volumes/SSD990/cryptanalysis/sage -python \
  experiments/ecc2k130-normal-weight4-base-20261009/verify_sage.py \
  --result /tmp/ecc2k130-weight4-producer.json \
  --runtime-info /tmp/ecc2k130-weight4-runtime.json \
  --out /tmp/ecc2k130-weight4-verification.json
```
