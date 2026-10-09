# Fixed-width radix-943 recoder comparison

## Candidate

Keep the secp256k1 scalar reduction, nearest Eisenstein lattice
representative, radix-943 unit-orbit atlas, thirteen precomputed point tables,
point additions, and affine recovery identical to the existing radix-943
path. Change only the online coefficient updates from allocated `BigInt`
remainder/subtraction/division to a signed three-limb magnitude. Each limb is
64 bits. Compute the Euclidean remainder modulo 943, select the same atlas
digit, subtract that signed digit, and divide exactly by 943. Preserve the
existing path as the reference and expose the candidate through separate
opt-in fixture and case flags.

The same binary must run both modes on the same public scalar fixtures.
The benchmark timer starts after parsing and table preparation and includes
scalar reduction, lattice representative selection, every recoder step,
lookup, unit action, point accumulation, final affine conversion, and the
expected-point assertion. Record preparation and retained table memory
separately. A measured online ratio requires the repository's strict
isolated-benchmark service receipt; local timings are diagnostics only.

## Correctness gates

1. For signed values at zero, the sign transition, 64-bit and 128-bit limb
   boundaries, and near the 192-bit capacity, compare the word remainder and
   exact quotient against `BigInt` arithmetic. Include negative values and
   digits on either side of the Euclidean remainder.
2. Replay all 129 frozen fixture scalars through both dispatches. Compare
   each of thirteen selected digits and orbit/unit codes, final coefficient
   zero, point, addition count, retained bytes, and expected fixture point.
3. Replay at least 512 fresh deterministic reduced full-range scalars plus
   `0,1,2,n-2,n-1,n,n+1`. Compare both modes' digit streams and output
   points; independently multiply at least 128 fresh scalars by the generator.
   Freeze the seed and input digest before any timing comparison.
4. Run the standalone native Rust test suite and both opt-in benchmark-case
   dispatches. Save exact source, fixture, binary, input, stdout, stderr,
   exit-code and test-log hashes in a verification receipt. Preserve failures.

The candidate retains the 1,926,717 point slots and 140 MiB cap of the
radix-943 format. A speedup decision waits for paired full-operation online
times under the strict CPU isolation gate. The mathematical point-addition
count is unchanged; this experiment targets allocation and division cost in
the recoder.
