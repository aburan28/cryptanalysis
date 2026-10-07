# Fresh global-gauge stride experiment

The existing `validate_scalar.py` evaluator chooses a carried unit
orientation locally. `compare_global_gauge.py` keeps the same curve,
short lattice pair, unit digits, Jacobian formulas, and mixed-addition
path, but computes a minimum-cost orientation and stride schedule
across the *entire* digit stream. It compares that schedule with the
existing local carried-gauge evaluator on eight new bases and sixteen
new scalars per base. The SHA-256 input label is fixed in the source.

After the highest nonzero digit, a state is `(digit_index, gauge)` with
three possible gauges. A one-step transition consumes one digit and
costs `4M` plus one digit-rotation multiplication when needed. A legal
two-step transition requires the higher of its two digits to be zero,
consumes both positions, and costs `7M`, or `6M` when the orientation
change is two, plus any digit rotation. Either transition may choose
the next gauge. Initial digit rotation and final gauge removal are
charged. The recurrence enumerates all legal transitions and takes
the minimum; mixed-addition counts are identical across schedules and
are added back to the full frozen formula count.

The formula boundary is exactly the one in `STAGE_MEASUREMENT.md`:

`4*tau_steps + 8*mixed_adds + digit_rotations + final_rotations
 - tau_pairs - cheap_z_pairs`.

The experiment checks every local and global output against Sage's
independent `kP`, verifies identical τ-step and mixed-add counts, and
records every scalar, point, counter, source hash, and failure. The
global formula count must be no larger than the local one on each case.
The run records no CPU timing. Recoding and schedule-search overhead,
squarings, exceptional paths, setup, normalization, and Python/Sage
costs are outside this stage count. The source paper's optimized
Jacobian `τ` formula and state-of-art full scalar implementations are
not represented by this local-policy control.

Freeze this protocol and source before deriving the new input set.
Then save the accepted Sage runtime receipt and run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/global-gauge-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/compare_global_gauge.py
```

A positive formula difference is a structural diagnostic only. A
speedup claim requires complete native operations and the repository's
host-isolated CPU receipt. A negative or zero result remains in the
record.
