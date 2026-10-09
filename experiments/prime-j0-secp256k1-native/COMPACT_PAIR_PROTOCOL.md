# Compact affine storage for orbit-pair tau comb: frozen protocol

## Candidate

Replace each 432-byte affine `Jacobian` table slot in PR #529 with four
signed field coefficients. Store three 64-bit magnitude limbs per coefficient
and pack their four signs into one byte. The representation is expected to
occupy 104 bytes per slot on the target 64-bit build. Reject table
construction if any coefficient needs a fourth magnitude limb; never
truncate. Decode a selected slot to the exact existing affine `Jacobian`
before applying its common unit and mixed addition. Keep the 236,196 point
values, 13-column schedule, hex9 selection, top repair, and operation count
unchanged. This is a public-scalar lookup method.

## Frozen comparisons and acceptance gates

- Reference: commit `cf527cca46f4cbf6b3491bb648aaafcdca5dfb31` (PR #529).
- Candidate source and release binary must have recorded SHA-256 receipts.
- Inputs: boundaries `0,1,n-1,n,n+1`; 214 frozen parent scalars; all 129
  expected-point benchmark fixtures; 2,048 fresh scalars from Python
  `random.Random(20261009131).randrange(n)`.
- Every complete native JSON output must match the reference. At least 256
  fresh/boundary points must also match independent Python secp256k1
  multiplication; all 129 fixtures must match their recorded point.
- Native release tests must pass, including a table-entry round trip for a
  deterministic sample from each row pair. Runtime packing validates all
  236,196 entries before any candidate scalar is evaluated.
- The prepared table must contain exactly 236,196 slots and use at most
  30 MiB of retained slot storage. Report table construction wall time and
  child peak resident memory. A preparation failure or over-limit result
  stays in the record.
- Generate a paired manifest with the same 129 fixture points and
  seven repetitions. Controlled online CPU timing requires the host-level
  isolation and noise gates in `docs/ISOLATED_BENCHMARKS.md`. The local
  correctness and resource checks do not establish a wall-time speedup.
