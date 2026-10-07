# Fresh 256-bit paired-stride stage diagnostic

`compare_stage.py` fixes eight bases and sixteen fresh scalars per
base from its committed SHA-256 label. For each scalar, the control
and candidate share the short lattice pair, τ-adic unit digits,
free unit-gauge policy, and the same
explicit Jacobian mixed-addition and τ formulas. The candidate alone
fuses adjacent τ steps when the higher digit is empty and may carry
the gauge through that stride. Both outputs must equal Sage's
independent `kP`; τ step and mixed-addition counts must match.

The frozen nominal field-multiplication boundary is

`4*tau_steps + 8*mixed_adds + digit_rotations + final_rotations
 - tau_pairs - cheap_z_pairs`.

This is a formula count for the evaluator only. It excludes
squarings, exceptional add paths, lattice reduction, digit recoding,
preparation, table lookup and branch costs, normalization/inversion,
and Sage/Python overhead. The 128 outputs are stage diagnostics, not
the primary one-target rho workload. No CPU timing or speedup claim
is made from this script.

Freeze this file and `compare_stage.py` before execution. Save the
checked Sage runtime receipt, then run the committed script:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/stage-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/compare_stage.py
```

Preserve every per-case scalar, point, formula count, success, and
failure. A positive structural saving would justify a native
full-operation prototype; it would not establish CPU speed or
academic novelty. The host-level isolation gate remains required for
any wall-time ratio.
