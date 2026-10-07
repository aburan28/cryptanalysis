# Batch-normalized paired-lattice rho startup

## Frozen question

The one-target j=0 rho solver creates eight target-dependent multiplier
points `M_i = alpha_i P + beta_i Q` before walking. The paired2 startup
currently normalizes each joint τ result separately. Evaluate all eight
in Jacobian form, then normalize the table with one batch inversion.
Keep the same joint point preparation, paired2 scalar recoding, coefficients,
walk table, restart method, fixed seed, cap, and verification. This is an
opt-in `TAU_PAIRED2_BATCH` API mode; the default solver is unchanged.

Charge all batch prefix/product multiplications and the one inversion to
the target-dependent online interval. Count actual table output inversions
separately from restart output inversions, along with τ steps, mixed adds,
rotations, recodings, pair scores, batch size, and reference-equivalent
budget operations. The rho operation cap uses the unchanged reference
equivalent budget so a fixed seed follows the same walk. The expected
algorithmic saving is seven output inversions for an eight-point table;
batch normalization adds field multiplications, so a wall-time win is a
hypothesis rather than a conclusion.

## Single-target gate

Freeze a fresh public `glv-j0-32` target and known-scalar certificate using
the independent Python affine group law, before running any candidate.
Pass only the public point and fixed rho seed to the executable. Each
invocation starts with an empty distinguished-point table. Run
`reference,paired2,paired2-batch,paired2-batch,paired2,reference`
serially, keeping every raw result. Require identical recovered scalar,
independent replay, table entries, reference-equivalent group operations,
table/restart evaluation counts, and target/seed echoes.

Release and UBSan tests must cover batch output against individual paired2
and generic affine multiplication, including zero scalars, identity,
same/opposite points, cancellation, and order boundaries. This local
panel is a correctness and algorithmic diagnostic. CPU timing on an
unverified host remains exploratory; only a strict receipt from
`docs/ISOLATED_BENCHMARKS.md` can promote a speedup. Academic novelty
is not claimed for batch inversion.
