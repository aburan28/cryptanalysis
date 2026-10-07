# Native single-use seed-format comparison

Freeze native source, this protocol, and the correctness runner before
executing. Compare two native formats on the same secp256k1 scalar/base
input: `cached_projective` keeps the nine constructed seeds projective,
caches used `Z²,Z³`, and uses cached Jacobian additions; `all_affine`
batch-normalizes the eight constructed non-base seeds with one
preparation inversion and uses mixed additions. Both arms use the same
native short lattice representative, width-four digits, optimized seed
chain, unit orbit, paired-τ stride, Montgomery field, and final affine
conversion. The controlled variable is the seed format and associated
addition/preparation cost, not the published digit method as a whole.

First build once offline and run `--check-benchmark-case` for both arms
on every case in the already frozen 64 original, 30 edge, and 256
held-out fixtures. It must recompute native representatives/digits,
check all nine prepared points against Sage, recover the exact saved
scalar point, and retain each raw exit. This path prints no timing.
Then derive the minimal 64-case one-use benchmark workload from the
original fixture. Each case carries only a base point, scalar, and
expected output; it supplies no prepared seeds or recoded digits.

For isolated timing, the benchmark process reads and parses the minimal
workload before starting the internal timer. The timer starts before
base/scalar decoding, then includes native lattice reduction, width-four
recoding, one-use seed construction, orbit/cache or batch normalization,
point evaluation, final affine conversion, and comparison with the
independently frozen expected output. It stops only after that check.
Both arms must report the same base, scalar, and output. Process launch,
fixture loading, and curve-wide constants are outside the interval.
Submit a manifest with alternating paired order to the repository's
isolated benchmark service; only a passing host-isolation receipt may
support a CPU ratio. A paired result here compares these two formats,
not the fastest available GLV/libsecp256k1 implementation or a
secret-scalar-safe API. Preserve failures and noise-gate rejections.
