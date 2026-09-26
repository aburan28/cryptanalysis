# An FPGA Pollard rho core for ECC2K-130

A synthesisable walker for the Certicom ECC2K-130 challenge: the
Bailey–Batina–Bernstein–… iteration on the Koblitz curve

```
E : y² + xy = x³ + 1      over  F_{2¹³¹}
```

together with a golden C model, testbenches that compare the two value by
value, a host tool for the campaign side, and measured area and cycle counts.

**What is verified and what is not.** Every arithmetic claim below is checked
in simulation against the model, and the model is checked against field
axioms and two independent facts about this curve. The area numbers come from
yosys mapped to 4-input LUTs. There is **no vendor place-and-route here, so
there is no fmax, no device utilisation and no points-per-second figure** —
those need Vivado or Quartus and a real part, and a number quoted without them
would be a guess. See [Numbers](#numbers).

## Why a normal basis, and why this one

`F_{2¹³¹}` is carried in a **type-II optimal normal basis**, which exists
because 2·131+1 = 263 is prime and 2 has order 131 mod 263 (so 2 generates the
quadratic residues). With γ a primitive 263rd root of unity the basis is
`βᵢ = γⁱ + γ⁻ⁱ`, i = 1…131, and an element is a 131-bit vector.

Three consequences, and the design is built on all three:

| fact | consequence in hardware |
|---|---|
| `βᵢ·βⱼ = β_{i+j} + β_{i−j}` (indices folded by `β_{263−k} = β_k`, `β₀ = 0`) | a product is a **cyclic convolution** of two symmetric 263-bit vectors: shift-and-xor, and a digit-serial unit does it |
| `βᵢ² = β_{2i mod 263}` | **squaring is a permutation** — free, it is wiring — so the Frobenius the whole attack is built around costs nothing |
| the normal-basis order is a permutation of this index order | the **Hamming weight is the same in both**, so the iteration's `j` and the distinguished-point test read the vector the hardware already holds, with no conversion |

None of that is taken on trust. `model/ecc2k130_test.c` builds the field
independently and checks the basis, the product rule, the squaring
permutation, that `1` is the all-ones vector, and that the trace of an element
is the parity of its weight. The curve is identified the same way, by
derivation rather than by quotation: `E₀(F₂)` has 4 points, so the Frobenius
trace is `t = −1`, and the Koblitz recursion `s_m = t·s_{m−1} − 2·s_{m−2}`
gives

```
#E(F_2^131) = 2^131 + 1 − s_131 = 4 · 680564733841876926932320129493409985129
```

with that cofactor-4 quotient prime (~2¹²⁹). The test then checks the two
facts that make this *this* curve: `σ² + σ + 2 = 0` on every point (the
Frobenius acts as τ), and `n·P = O` for points multiplied by the cofactor.

## The walk

```
j  = ((HW(x_R) >> 1) & 7) + 3          j ∈ [3, 10]
R' = σ^j(R) + R                        σ(x, y) = (x², y²)
distinguished ⟺ HW(x) ≤ 34
```

One step is therefore one affine addition: **one inversion, two
multiplications and a squaring**, since σ^j is wiring. The inversion is
Itoh–Tsujii along the chain 1, 2, 4, 8, 16, 32, 64, 65, 130 — eight
multiplications — so a step is about eleven multiplications and the inversion
is 70% of it. That ratio is the single most important number in this design
and is what a larger one would attack first; see [What is not
here](#what-is-not-here).

Only `x` is reported. On a Koblitz curve `−(x, y) = (x, x+y)`, so `x` is
already the negation-class invariant; the Frobenius class is normalised
host-side by taking the minimum over the orbit, which is 131 cheap
permutations on a CPU and a lot of gates on an FPGA. No coefficients are
tracked: a walk is identified by its seed and a collision is resolved by
replaying both walks, which is the trade every ECC2K-130 implementation makes.

The exceptional case `σ^j(R) = ±R` makes the denominator zero. The core does
not divide anyway — it raises `exc` and stops, and the host loads a new start
point. Dividing would produce a point that is not on the curve, which the core
would then report as a distinguished point, and nothing downstream would catch
it.

## The design

```
ecc2k130_top      N cores, a round-robin collector, a register file
  ecc2k130_core   one walk: state, back-pressure, counters
    ecc2k130_step j from the weight, σ^j, the affine addition, the DP test
      onb131_inv  Itoh-Tsujii, over the core's one multiplier
      onb131_mul  digit-serial cyclic convolution  (DIGIT bits per cycle)
      onb131_frob{,_j}  the Frobenius: permutations, i.e. wiring
```

- **One multiplier per core.** The inverter and the step FSM never hold it at
  the same time, so the arbitration is a mux and not a scheduler.
- **Back-pressure stops the walk; it never drops a point.** A dropped point is
  walk time that was paid for and lost, and nothing downstream could detect it.
- **The collector is round robin**, and for a reason beyond fairness: a
  starved core stops walking (its own back-pressure stops it), so a
  fixed-priority arbiter would quietly reduce a fleet of cores to one.
- **`points` counts points produced**, including one still sitting in the
  output register — a host comparing the counter against what it has received
  must drain the stream first. (The top-level testbench does, after finding
  out the hard way.)

`ecc2k130_top`'s register port and point stream are the boundary with the
board: AXI4-Lite and AXI4-Stream on a Zynq or Alveo shell, a PCIe DMA engine,
or a UART on something small. Nothing above that line is vendor-specific,
which is why the whole thing simulates with open tools.

## Numbers

Measured here, on this machine, with the tools named. Every row's RTL passed
the full vector comparison against the model.

**Latency** — Icarus Verilog, cycles per operation, `DIGIT` bits of the
convolution per cycle:

| DIGIT | cycles/multiply | cycles/inversion | cycles/step |
|---:|---:|---:|---:|
| 1 | 132 | — | 1342 |
| 2 | 67 | — | 692 |
| 4 | 34 | 289 | 362 |
| 8 | 18 | — | 202 |
| 16 | 10 | — | 122 |

**Area** — yosys, technology-independent synthesis mapped to 4-input LUTs.
These are *not* vendor numbers: no place-and-route, no timing, no device.

| build | LUT4 | flip-flops |
|---|---:|---:|
| 1 core, DIGIT=1 | 7,301 | 4,126 |
| 1 core, DIGIT=2 | 7,561 | 4,125 |
| 1 core, DIGIT=4 | 7,941 | 4,124 |
| 1 core, DIGIT=8 | 8,607 | 4,123 |
| 1 core, DIGIT=16 | 10,045 | 4,122 |
| 2 cores, DIGIT=4 | 15,705 | 7,887 |
| 4 cores, DIGIT=4 | 31,437 | 15,415 |

Two things worth reading off these tables. Cores scale linearly in area, as
they should — they share nothing. And **a wider digit is a better trade at a
fixed clock**: from DIGIT 1 to 16 the cycles per step fall 11× while the area
grows 1.38×, so the area–time product improves about 8×. That conclusion has
one large caveat, stated because it is the caveat that matters: a wider digit
lengthens the combinational path through the rotation network, and whether the
clock survives it is a question only vendor timing analysis answers. The
sensible next step for a real board is to sweep DIGIT under Vivado and find
where fmax starts to fall.

What is deliberately *not* quoted: iterations per second, points per day,
"break time", or a comparison against the GPU and CPU implementations in the
literature. All of those need an fmax this flow cannot produce, and the
honest form of that claim is a measurement on a board, not an extrapolation.

## Running it

```sh
cd fpga
scripts/run_sim.sh            # model self-test, vectors, every testbench, host tools
scripts/run_sim.sh 16 60 128  # DIGIT=16, relaxed DP weight, 128 cases
scripts/synth.sh 4 8          # 4 cores at DIGIT=8: yosys area report
verilator --lint-only -Wall -Irtl --top-module ecc2k130_top rtl/*.v
```

Needs `iverilog`, and optionally `verilator` and `yosys`. No vendor tools and
no licences.

**The distinguished-point weight in simulation.** A campaign runs at weight
34, which yields a point about once in 2²⁵ steps — nothing a simulation will
ever see. The cutoff is a parameter of both the model and the RTL (`DPW`), so
the testbenches run both sides at a relaxed weight and are still comparing the
same rule; only how often it fires changes.

## The host side

```sh
host/ec2k start  --seed 7                       # a start point for a core's load window
host/ec2k walk   --seed 7 --steps 100000 --out unit-7.bin
host/ec2k verify --seed 7 --steps 100000 unit-7.bin
host/ec2k merge  unit-*.bin
```

`verify` is what makes an untrusted accelerator usable: the host replays the
walk in software and requires every point the board reported to appear. One
replay per point, against the 2²⁵ steps that produced it. A board that is
broken, overheating or fabricating records is caught here, rather than by a
campaign that quietly never collides — and `scripts/run_sim.sh` checks that
the check can fail, by feeding it another walk's records.

`merge` reports the campaign's terminal event: two records with the same `x`
from different seeds are two walks that met. Turning that into a discrete
logarithm means replaying both walks with coefficients, which is deliberately
not automated: it happens once, and it is worth a person watching.

## Where this fits with the rest of the repository

The library's [distributed protocol and coordinator](../docs/COORDINATOR.md)
schedule work for groups of order below 2⁶⁴ — that is the library's own
limit, and ECC2K-130 is a 131-bit field. So these are *not* wired together,
and pretending otherwise would mean a control plane that cannot represent
the campaign it is scheduling. What
they share is the shape: a replayable unit identified by a seed, a fixed-width
record with no framing, verification before anything enters a corpus, and a
merge that is the only place a collision becomes an answer. `ec2k walk`
produces 32-byte records for the same reason `ca dist-walk` does, and an agent
that drove a board instead of a CPU would report them the same way.

## What is not here

- **Batched inversion.** One step is ~11 multiplications and 8 of them are the
  inversion. Montgomery's trick amortises one inversion across *n* walks at
  the cost of 3(n−1) multiplications, which would take a core from ~11
  multiplications per step to ~4 at n = 8 — nearly 3× — at the cost of holding
  n walk states. This is the single biggest improvement available and it is
  the next thing to build.
- **Vendor place-and-route**, and therefore any throughput number. See
  [Numbers](#numbers).
- **A board interface.** The register port and the point stream are the
  boundary; the DMA, the PCIe shell and the driver belong to a particular
  platform.
- **The challenge's own base and target points.** The core takes start points
  from the host, which is what a campaign does; the published challenge
  parameters belong in a campaign definition, not in RTL.
- **Any claim about breaking ECC2K-130.** The expected work is ~2⁶⁰·⁹
  iterations. This is a verified core and a measured area, not an attack in
  progress.
