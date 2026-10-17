# Three-bucket affine digit panel on RunPod

The norm-4,831 three-bucket scalar format retains **1,425,154 bytes**, a
515,840-byte (26.6%) reduction from the direct two-x format. A five-point,
25-pair Linux panel found a reference/three-bucket online-time median below
one on every point. The table reduction is therefore useful as a memory
option; the measured operation mix favors the direct two-x evaluator for
online time on this allocation. The current runner omitted the A/A
calibration required by the [Tier 1 contract](../../docs/IC_BENCHMARK_TIERS.md),
so these timings remain exploratory even though its per-job receipts say
`tier1` and `valid`.

## Frozen comparison

The public curve is secp256k1 over its 256-bit prime field. Both programs use
the same norm-4,831, 20-step fixed-base scalar recoding, fused terminal,
affine output, and 128-case fixture (`SHA-256
7f4672b7b676969fe40056d0f14c6ecf45ad36109870cdf3466ebafd9e7b22d8`).
Five fixture cases unused by the pod's prior jobs, indices 2 through 6,
were frozen before submission. Each case ran five alternating
reference/candidate pairs through the same serial queue, one case at a time.
The runner pinned each process to exposed CPU 14, used NUMA node 0 and a
300-second cap, and recorded cgroup, frequency, interrupt, steal, resource,
and verification fields. The allocation was RunPod Secure Cloud CPU flavor
`cpu3c`, eight exposed vCPUs, 16 GB RAM, Ubuntu 24.04 image, and Rust 1.99.0
on x86-64 Linux. A Pod does not prove physical-host exclusivity.

The online clock includes scalar-dependent recoding, digit selection, point
addition, terminal handling, and affine recovery. It excludes fixture load,
table preparation, and the independent expected-point comparison for both
arms. Mean preparation time was 4,561 ms for direct two-x and 4,545 ms for
three-bucket across the 25 runs per arm. The separate preparation receipt
must be considered for cold-start use.

| Fixture case | Valid pairs | Direct mean online (ms) | Three-bucket mean online (ms) | Median direct/three-bucket | Pair bootstrap 95% interval |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 5/5 | 0.040049 | 0.044560 | 0.870 | [0.795, 1.007] |
| 3 | 5/5 | 0.039797 | 0.043260 | 0.916 | [0.865, 0.969] |
| 4 | 5/5 | 0.039057 | 0.041641 | 0.936 | [0.848, 1.041] |
| 5 | 5/5 | 0.038927 | 0.040894 | 0.925 | [0.863, 1.085] |
| 6 | 5/5 | 0.036818 | 0.041507 | 0.911 | [0.787, 0.976] |

The ratio is `direct_online_ms / three_bucket_online_ms`; one would favor
three-bucket. Each displayed interval resamples only the five pairs for
that named point. It is descriptive and does not replace the missing A/A
calibration. Across all 25 runs, mean online time was 0.038930 ms for direct
two-x and 0.042372 ms for three-bucket. The exact individual pair ratios,
outer elapsed times, stdout, stderr, preflight, counters, and failure fields remain
in the [raw receipt bundle](raw-receipts.tar.gz).

## Verification and gate finding

Both Linux release binaries passed the five native test families, including
4,831 residue codes, 43,479 quotient cases, 96,720 three-bucket unit images,
5,680 terminal indices, the 128-case frozen fixture, and 518 additional
scalar replays. The two-x test run retained 1,940,994 bytes. The generated
source revision was `b87f5701e0ea3271580fd72bb9a414eb6ac5f60f`;
the reference binary hash was
`43efa1290e578aacad498143f436b523af009919130879924b7fde613ee329eb`
and the three-bucket binary hash was
`bde297c80ae22aa1bbe4399cfe21499e07aceaf6ff795d5734d9ecef3637c411`.
The runner hash was
`48361f0d0a5138e9e2f1264ff3de689fddb9d1a5181afd089e70c153e3a089cc`.

[verify_receipts.py](verify_receipts.py) checks the bundle hash, every
manifest and summary binding, 25 pair ratios and 50 valid run rows, exact
expected outputs, and five independent scalar multiplications from the
standard generator. It prints `aa_calibration=missing` because the archived
runner has no A/A calibration implementation or receipt. The runner also
assigns `speedup_qualified` within a one-case job, while the current Tier 1
contract requires a panel across five distinct points. Its run rows also
omit raw start and stop timestamps. These gates need implementation and a
fresh panel before promoting a cloud timing result.

The [panel index](panel-index.json) maps every case to its job ID and
contains all individual pair ratios. Reproduce the receipt audit with:

```sh
python3 experiments/prime-j0-three-bucket-tier1-20261014/verify_receipts.py
```

The next arithmetic experiment should remove the two projective bucket
joins or otherwise reduce charged field multiplications while retaining the
64-byte affine digit rows. The current 20-digit case uses 18 nontrivial mixed
additions, two projective joins, and two bucket rotations, whereas direct
two-x uses 20 mixed additions. The two joins explain why reduced table
traffic alone did not yield a lower measured online interval here.
