# Joint two-orbit τ atlas: source-count gain and native correctness

The candidate, protocol, and native mode were frozen in `cf60457b`
before the 256-case held-out score and native replay. Slots 5 and 6 of
the nine-orbit width-four table are now `2*(P−2τP)` and
`4*(P−2τP)`, replacing `P+2τP` and `2P+4τP`. Both replacement orbits
cover exactly the original slots' residue classes modulo `τ⁴`. The
global recoder termination audit has **817 closed-ball states** at
Eisenstein norm at most 224 and no nonzero cycle; strict norm descent
handles all states outside that ball.

The source-count model charges five point doublings, three mixed
additions, two unit rotations, and nine orbit-image multiplications:
`5*7 + 3*11 + 2 + 9 = 79 M+S` of one-use preparation. The original
table charges `4*7 + 4*11 + 2 + 9 = 83 M+S`. Evaluation charges paired
τ steps, solo τ steps, mixed and cached projective additions, and the
used seed caches. Both arms use the same coefficient-lattice reduction
and a final affine inversion, which are **outside this count**. The
native one-use CPU interval must include them.

| Frozen input panel | Cases | Original `M+S` | Joint atlas `M+S` | Saving | Per-case signs |
| --- | ---: | ---: | ---: | ---: | --- |
| Original design, 64 distinct bases | 64 | 88,656 | 88,313 | 343 (0.387%) | 35 faster, 28 slower, 1 tied |
| Held-out, 8 bases × 32 scalars, with preparation charged to every scalar | 256 | 355,187 | 354,090 | 1,097 (0.309%) | 161 faster, 91 slower, 4 tied |

The held-out paired mean saving is **4.29 `M+S` per scalar**. A
10,000-resample paired bootstrap over these 256 saved cases, seeded
with `20261007`, gives a descriptive 95% interval of **2.19–6.34**
units per scalar. This describes input variation under the saved
fixture law; it is not CPU timing uncertainty. The exact per-case rows,
input/source hashes, and operation counts are in `joint-atlas-result.json`.

The checked repository Sage launcher wrote
`alternate-runtime-info.json` with `status: verified` before generating
independent alternate seed points for all **350** original, edge, and
held-out cases. The Sage seed fixture SHA-256 is
`54da3257da0c37f50bc61b58714415b59124af36e619aa891c219301b2672f01`.
The offline release binary on macOS ARM64 (`rustc 1.93.1`) has SHA-256
`91e5b4dda8da777ed3757e82cf329b6b0170454f2db72cd7975c3d16b8d929a2`.
It checked all **3,150 prepared seed points** and **350 final scalar
points** against Sage, with no exceptional cached additions. The
native source counts exactly match both design and held-out Python
totals. The original 64-case native path still passes its saved
representative, digit, seed, output, and count checks. All commands,
exits, stdout/stderr, hashes, compiler, and host details are in
`native-joint-checks.json`.

`make_joint_manifest.py` generated a 64-case paired manifest comparing
the original cached-projective path with the joint atlas. The
`isolated_bench.require_manifest` **structural** check passed using a
synthetic CPU/NUMA/cgroup description. No host isolation preflight or
CPU timing ran. The manifest is a handoff template; fill it with the
actual physical host partition and build the native crate on that host
before submission. `cpu_speedup_claim` remains null, and this
variable-time research code is not a secret-scalar implementation.

The construction is an alternate digit and seed-preparation choice
inside the published τ-adic/endomorphism family. Independent
prior-art review would be needed for an academic novelty claim;
`academic_novelty_claim` remains null.
