# Fixed-width 25-representative tau comb

Selecting the least expensive of 25 congruent Eisenstein representatives
reduces the complete point-evaluation proxy of the 1,024-point secp256k1
tau-six comb from **3,252,317 to 3,131,520 field-product units** on a fresh
10,000-scalar panel. The recoding search uses signed three-limb integers and
packed stack digit streams; the selected stream uses the existing two-point
terminal cover. The affine table remains at **1,024 points**.

This is a **3.71% reduction in the point-evaluation proxy** on that panel.
The 25-representative search itself is charged by the native case timer but
is not represented by the point proxy. A CPU wall-time result requires the
paired isolated-host receipt described below.

## Algorithm and bounds

For public scalar `k`, form the 25 lattice representatives indexed by
`(du,dv) in [-2,2]^2` around the rounded inverse-lattice center. Every pair
`(a,b)` satisfies `a+b*lambda_tau = k (mod n)`. Recode each pair with the
frozen width-six atlas. Reject streams longer than 162 positions and streams
with more than one top-row digit. Score each remaining stream as
`5*tau_steps + 11*(mixed_additions + top_repair)`, breaking ties by norm rank.
Evaluate the selected stream in the 13-column comb; an omitted top digit is
the exact sum of two retained top-row unit images.

The nearest lattice representative is in the 25 candidates and has the
previously proved 162-position span and at most one top-row digit. The
two-sum cover handles every omitted top orbit. Therefore at least one
candidate is eligible for every scalar, and selecting the minimum score
cannot increase this point-evaluation proxy over the nearest-representative
cover. The selected pair remains congruent to `k`, and the digit expansion
reconstructs that pair exactly.

The three-limb recoder has ample exact range. Rounding plus offsets of at
most two give `|a| <= 5/2*(|u0|+|v0|) < 2^130` and
`|b| <= 5/2*(|u1|+|v1|) < 2^130` for the frozen basis. Thus the Eisenstein
norm `a^2+3ab+3b^2` begins below `2^263`. A zero tau step divides the norm
by three. For a nonzero width-six digit, its norm is at most 217 and the
quotient divides by `tau^6=-27`; the norm triangle inequality gives
`sqrt(N(next)) <= (sqrt(N(current))+sqrt(217))/27 < sqrt(N(current))`
for every nonzero integral state. Consequently both recoding coordinates
remain below `2^133` in magnitude. The signed 192-bit arithmetic also checks
addition overflow and exact division at runtime. The selected algorithm is
variable-time and is intended for public scalars.

## Frozen operation record

| Panel | Scalars | Nearest cover proxy | Cover25 proxy | Selected repairs |
| --- | ---: | ---: | ---: | ---: |
| Frozen edges | 22 | 1,838 | 1,801 | 0 |
| Frozen design random | 64 | 20,776 | 20,016 | 0 |
| Frozen holdout random | 128 | 41,722 | **40,145** | 3 |
| Disjoint random, seed `2026100945` | 10,000 | 3,252,317 | **3,131,520** | 274 |

On the disjoint panel, 7,689 scalars select a representative other than the
nearest. The deliberately omitted-orbit scalar moves from **335 to 308**
proxy units by selecting rank three, which uses 11 tau steps, 23 mixed
additions, and no repair. The independent Python screen verifies **535**
native points, including all 214 frozen scalars, the deliberate omission,
the first 256 disjoint scalars, and up to 64 further selected repairs. All
**45** native release tests pass, including a comparison of the fixed-width
recoder with the arbitrary-precision recoder on every one of 25 nearby pairs
for boundary scalars.

The paired isolated manifest compares the nearest-cover and cover25 modes
on the same 129 public scalar fixtures. Its timer includes lattice search,
all 25 recodings, score selection, point evaluation, affine conversion, and
the expected-point assertion. The current RunPod container fails the strict
host-isolation preflight, so these operation counts remain separate from a
controlled CPU speedup result.

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/Volumes/SSD990/crypto/target-cover25
cargo test --offline --locked --release --bin eisenstein_fixed
cargo build --offline --locked --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 tau6_comb13_cover25_screen.py \
  --binary "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /Volumes/SSD990/crypto/new-cover25-result.json
```

The frozen result SHA-256 is
`240d6303a0360812b5935404fd9712beec6e6415552508df7fb0b586aa3e646e`.
The native source SHA-256 is
`9d060bd179b2cd775f38b3b78d4d0c7a562fd2b327875d3815fc75772bb0a443`;
the release binary SHA-256 is
`6ef93f7c9349259b812ebf8aaf396fedbc64ca70efaeff0f0ce9827fbb60d7d3`.
