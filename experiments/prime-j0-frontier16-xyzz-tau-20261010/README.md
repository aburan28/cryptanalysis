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

On the same 4,096-scalar panel, the sixteen-window evaluator used 65,536
digit terms and 532,480 field multiplications in its point kernel. The
seventeen-window control used 69,627 digit terms and 565,198 multiplications.
The candidate therefore saved **4,091 digit terms, 32,718 multiplications,
and 8,179 squares** across the panel. Its retained table plus atlas is
11,786,576 bytes versus 6,615,956 bytes for the seventeen-window control.
`verify_ops.py` replays the temporary counter patch against the frozen source
and checks the recorded counts; the shipping source contains no counters.

Operation counts and table bytes are algorithmic diagnostics. A CPU wall-time
comparison requires the host-level isolation receipt in
`docs/ISOLATED_BENCHMARKS.md`.
