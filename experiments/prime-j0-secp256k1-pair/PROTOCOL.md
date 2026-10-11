# 256-bit secp256k1 check for carried-gauge paired τ

The small-field C experiments use the endomorphism
`τ = 1 - ω` on curves `y² = x³ + b`. This check evaluates the same
Jacobian τ, tripling, and paired-τ/Z-gauge formulas over secp256k1's
256-bit prime field, then compares each output with Sage's independent
elliptic-curve group operations.

`validate.py` fixes 64 nonzero subgroup scalars from its committed
SHA-256 label. For each point it checks the identity
`τ²(P) = -3ω(P)`, three projective input scales, one τ output,
one tripling output, and all three carried-gauge changes. The three
projective scales test coordinate independence, not just affine
inputs. The script records the point-input digest and source hash.
Commit this protocol and script before execution; save the checked
repository Sage launcher's `--runtime-info` output before running it.

Run from this repository worktree with the absolute checked launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-pair/runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-pair/validate.py
```

This validates these formulas at 256-bit field size. It does not run
the complete τ-adic scalar recoder, compare secp256k1 scalar outputs
end to end, measure CPU speed, or establish academic novelty. The
result keeps `cpu_speedup_claim: null`.
