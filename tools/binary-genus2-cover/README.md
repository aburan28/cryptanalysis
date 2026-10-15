# Binary genus-two cover and Jacobian transfer

Construct a cover of `E_a: y²+xy=x³+a*x²+1` over the **same binary field**:

```
C_a: v²+u²*v = u⁵+a*u⁴+u³+u
pi(u,v) = (u³/(u+1)², (u*(u+1)*v+u²+u+1)/(u+1)³).
```

The smooth projective source has genus two. Its infinity and points above
u=1 map to E's origin; (0,0) maps to (0,1). The curve is one-dimensional;
its Jacobian is an abelian surface, where the group law lives.

The library `GenusTwoCover` checks the model with the repository's existing
`HyperellipticCurve` and `MumfordDivisor` implementation, supplies the point
map, pulls elliptic point classes into the Jacobian, and inverts that image.
The library accepts validated polynomial-basis fields supported by the
backend and any coefficient a of that field; b is fixed to one. The CLI
only accepts the existing pinned GF(2^83) a=0/a=1 fixtures.

From the repository root:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml -- \
  --a both --output /tmp/genus2-n83.json
```

Default Q is the public fixture 37P. To transfer a supplied public point on
the **exact same model, basis and subgroup**, choose one a:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml -- \
  --a 0 --q-point 0x590a9c0709b34b0bcd3d4,0x6aa49dc52796827db931a \
  --output /tmp/genus2-supplied-q.json
```

Omitting `--scalar` in supplied-Q mode leaves both scalar fields null. Add a
known witness only to check it. Invalid input or a failed check exits 2.
The basis is `z^83+z^45+z²+z+1`. Exact subgroup orders are decimal strings;
field elements and ascending Mumford coefficients are hexadecimal strings.
For a=0 the command reuses the cited historical Sage prime receipt. For a=1
it performs a fresh deterministic u64 seven-base Miller–Rabin check.

For nonzero x, the reduced pullback is

```
U(u) = u²+(1/x)*u+x
V(u) = (x+(y+1)/x²)*u+x+y+1.
```

O maps to `(1,0)` and (0,1) to `(u,0)`. The checked inverse on this image
recovers x=U(0), y=V(0)+x+1, then reconstructs and compares the full pair.
A valid Jacobian divisor outside the image is rejected. Arbitrary-divisor
norms are not implemented. By Picard pullback this is a homomorphism; the
explicit inverse and uniqueness of reduced pairs establish injectivity.
Independently, `pi_* pi^*=[3]` proves injectivity on order-r subgroups with
gcd(3,r)=1, including both pinned fixtures.

Run `tools/binary-genus2-cover/check.sh` for formatting, native tests,
Clippy, CLI checks, and integer-lift identity replay. The exact identity
certificate has its own executable:

```sh
cargo run --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml \
  --bin genus2_identity -- /tmp/fresh-genus2-identities
```

The output directory must not already exist. See the
[protocol](../../research/binary_genus2_cover_20261014/PROTOCOL.md) and
[report](../../research/binary_genus2_cover_20261014/REPORT.md) for the
geometric proof, recorded checks, Lean proof scope, and PDF.

The construction checks establish the explicit map and subgroup transfer.
Full-subgroup solve records and their performance limits belong to the
separate campaign below. Field descent, arbitrary cover search and a faster
ECDLP algorithm remain unestablished. Arithmetic is variable-time research code.

## Full-subgroup ECDLP campaign

Use `cover_rho` when the request concerns solve costs on the elliptic subgroup
and its **genus-two pullback image**, rather than just map correctness. Read
the [campaign protocol](../../research/binary_genus2_speed_20261014/PROTOCOL.md)
before generating targets. This new command is a research campaign tool;
its native records are not sealed ecbench sessions. The
[integration gap](../../problems/ecbench-binary-genus2-full-subgroup-adapter.md)
tracks the remaining registry, common-cost and independent replay gates.

```sh
cargo build --release --locked --manifest-path tools/binary-genus2-cover/Cargo.toml --bin cover_rho
genus2_rho=tools/binary-genus2-cover/target/release/cover_rho
"$genus2_rho" generate --public /tmp/fresh-cover-public --witness /tmp/heldout-cover-witness.json
"$genus2_rho" replay --job /tmp/fresh-cover-public/a1-0.json --out /tmp/fresh-cover-replay
"$genus2_rho" calibrate --job /tmp/fresh-cover-public/a1-0.json --out /tmp/fresh-cover-rates --cpu 4
"$genus2_rho" reference --job /tmp/fresh-cover-public/a1-0.json --out /tmp/fresh-cover-reference --cpu 4
"$genus2_rho" verify --job /tmp/fresh-cover-public/a1-0.json --result /tmp/fresh-cover-reference/result.json --out /tmp/reference-verification.json
"$genus2_rho" run --public /tmp/fresh-cover-public --out /tmp/live-cover-campaign --cpu 4
```

Choose an available complete CPU core for `--cpu`; CPU 4 is the original
five-vCPU worker's selection, not a portable default. The driver takes the
native ecbench benchmark lock, attempts eviction, pins itself, and records
preflight, affinity, NUMA observations and hardware-counter availability.
VM observations are explicitly L0 and never establish a speedup.

`generate` makes eight uniform nonzero public targets per a with OS rejection
sampling. The witness file is separate, mode 0600, and is never an argument to
solver commands. Do not commit it or copy it into a solver input directory.
JSON jobs/checkpoints use exact integer decimal tokens; use a u128-aware
reader, not a floating-point JSON decoder. The solver rejects unknown fields,
including a scalar witness. It accepts only the pinned basis and generators.

`reference` is the unchanged optimized, batched signed-Frobenius rho with
cycle escape. It is a one-shot reference run with its declared step cap, not
a resumable process. `run` is the separately named resumable method
`rho.cover_image_checkpoint/v1`: unbatched elliptic additions, image inverse
plus the same elliptic walk, and checked native Cantor additions. The native
Jacobian arm selects canonical representatives through the checked image
inverse and pullback; these conversions are counted and timed on every step.
It measures this conservative implementation, not optimized Jacobian formulas
or index calculus. All arms quotient by the same 166 signed Frobenius actions.
`reference --arm image_inverse` includes the checked public-divisor round trip
before the optimized search. `reference-suite --public DIR --out DIR --cpu CPU`
runs one warmup, A/A controls, five interleaved direct/image-inverse pairs on
target 0, and one direct/image-inverse pair on each remaining a=1 target,
verifying every candidate in another process. Repeated controls do not add
independent targets. It leaves a=0 to the checkpointed campaign.

`run` schedules six streams serially, starts with target 0 for each arm/a,
and advances each stream through all eight targets after independent CLI
verification. Checkpoints include all distinguished points, coefficients,
lane histories, cursor and jump/start identity. Scheduling uses complete
lockstep rounds; elapsed time never changes the walk. Native divisor caches
are reconstructed losslessly from the image coordinates on resume. Checkpoints
are atomic and synced at least once per minute per active stream, on a
candidate, on pause and on an orderly stop. A crash may lose the current
minute of work. Checkpoints are trusted local state, not signed certificates.
The a=1 native Jacobian stream receives roughly 30-second quanta after its
first segment; other streams receive roughly two seconds. This prioritizes
the first native full solve while preserving a=0 progress. Scheduling changes
neither trajectories nor the target distribution. A large checkpoint write
or a long scheduler cycle can extend the interval between durable snapshots;
the actual checkpoint times and work counts are authoritative.

Create `OUT/PAUSE`, then wait for `OUT/paused.json` before copying checkpoints
or doing other heavy work. Remove `OUT/PAUSE` to continue. Create `OUT/STOP`
for an orderly checkpointed stop. To resume after exit, remove those control
files and repeat the identical `run` command; existing inputs are never
regenerated. Preserve `progress.jsonl`, host manifests and the binary/source
hashes alongside snapshots. A process on this worker is not a durable cloud
job and cannot survive the worker being deleted without moving checkpoints.

Calibration prefixes, theoretical birthday estimates and unfinished jobs are
never completed full-subgroup solve times. Additions in E and Jac(C) are
different native units; common priced work and speedup remain null.
