# Native 16-window two-bucket scalar evaluation

The native secp256k1 evaluator now uses the proved sixteen-window mixed-width
tau atlas from `prime-j0-tau-power16-20261010` with the two-X affine storage
and direct XYZZ endomorphism from the preceding formats. Its widths are fifteen
radix-256 windows and one final radix-512 window. The exact termination bound,
minimum cycle-cover construction, exhaustive residue checks, and independent
group replay are recorded in that earlier experiment's `PROOF.md` and
`group-check.json`.

The native table has **107,814** slots, of which 107,798 are nonidentity.
Every nonidentity slot was checked against a separately formed group sum in
the release test. The retained table and atlas size is **11,786,576 bytes**.
The mode is `153`; modes 132, 135, and 152 remain paired controls.

`make_inputs.py` draws the protocol's 4,096-scalar seed after source freeze and
rejects collisions with earlier scalar panels. `make_fresh_fixture.py` computes
each expected point with the independent affine binary implementation. The
replay checks those points, ten scalar boundary cases, and all 129 fixed
fixture cases across the candidate and three controls. The source receipt,
binary hash, compressed outputs, test logs, and point-operation diagnostics
are kept beside this note.

Operation counts and table bytes are algorithmic diagnostics. A CPU wall-time
comparison requires the host-level isolation receipt in
`docs/ISOLATED_BENCHMARKS.md`.
