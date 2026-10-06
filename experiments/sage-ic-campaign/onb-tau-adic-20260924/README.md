# Koblitz Frobenius scalar multiplication

For the exact curve `y² + xy = x³ + 1`, Frobenius `tau` satisfies
`tau² + tau + 2 = 0`. This change expresses scalars of at least 32 bits as
signed digits in `Z[tau]` and evaluates them with Frobenius and point
additions. It replaces the previous width-4 signed-window path in both
`ecc2k130/codegen/curves.py` and the tracked IC runner copy. The binary
loop remains for shorter scalars. No Sage installation or Metal kernel was
changed in this PR.

`baseline/` freezes the preceding signed-window implementation; `source/`
freezes the candidate. Both intent files were frozen before their measured
runs and bind the source, field, and benchmark hashes. Sixteen cells use
fresh Python processes, separate baseline and candidate field contexts for
first-call timing, then twelve alternating warm scalar calls. Every result
was checked against the preceding implementation and for curve membership.
`test_tau.py` checks the endomorphism identity, exhaustive small fields,
infinity, order-two points, negative scalars, threshold cases, and scalars
through 256 bits on both local and tracked runner copies.

The portable source and receipt check is:

```sh
python3 experiments/sage-ic-campaign/onb-tau-adic-20260924/verify_archive.py
```

Five targeted runner arithmetic tests passed. See `RESULT.md` for measured
scalar-call and first-call effects. Complete IC costs remain to be measured.
