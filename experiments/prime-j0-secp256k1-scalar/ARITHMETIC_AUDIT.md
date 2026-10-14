# Arithmetic audit of the 128-scalar stage comparison

The headline stage table in `STAGE_RESULT.md` counts field
multiplications `M` in the explicit evaluator, but excludes squarings
`S`. The exact source expressions used by this prototype give the
following **nominal generic-path** counts:

| Source operation | `M` | `S` |
| --- | ---: | ---: |
| One `jac_tau_scaled` | 4 | 2 |
| One `jac_tau_pair`, cheap Z orientation | 6 | 4 |
| One `jac_tau_pair`, other orientation | 7 | 4 |
| One generic `jac_add_mixed` | 8 | 3 |
| The first mixed-add call from infinity | 0 | 0 |

The recorded stream has 20,278 τ positions and 13,563 mixed-add calls
across 128 nonzero scalars. Each scalar's first call initializes from
infinity, so the generic-add formula applies to 13,435 calls. Both
arms therefore have the same nominal squaring count:

`S = 2 × 20,278 + 3 × (13,563 − 128) = 80,861`.

Removing the 128 initial additions from each arm's original `M`
count yields the following narrower arithmetic model. Rotations are
charged as in the frozen stage protocol.

| Arithmetic model, 128 scalars | Free-gauge no-pair control | Local paired/gauge candidate |
| --- | ---: | ---: |
| Generic-path field multiplications | 188,679 | 180,245 |
| Generic-path field squarings | 80,861 | 80,861 |
| `M+S` if one squaring costs one multiplication | 269,540 | 261,106 |
| Candidate saving under `S=M` | — | 8,434 (3.129%) |

This is still a **source-level model**, not a measured full scalar
cost. The counters do not distinguish exceptional mixed-add paths;
precomputation, recoding, table lookup, normalization/inversion,
constant multiplication details, and program overhead are absent.
The first-add correction follows directly from the source's infinity
branch. Different field kernels may have a different `S/M` ratio.

The key competitive issue is digit density. These 128 unit-digit
expansions average **105.96 nonzero digits** and 159.42 positions.
[Xu et al.](https://eprint.iacr.org/2024/1906), Section 4.3.2,
estimate a width-four nonzero density of about `1/4.5` for an
expansion of length approximately `log₃ n`, or roughly 36 nonzero
digits for a 256-bit scalar. Their paper's estimated total is
`<5.40 log₂ n + 94` multiplication equivalents under `S=M`, about
1,476 at 256 bits. That is an **analytic reference for a different
method and preparation policy**, not a paired measurement against our
source. It nevertheless shows why saving about 66 `M` per scalar in
the paired stride cannot, by itself, establish a competitive method:
the current stream makes roughly seventy more point additions per
scalar than the published sparse-digit estimate.

The next design should start from a sparse digit stream and a complete
arithmetic boundary, with the published method as an explicit
baseline. The current dense unit-digit evaluator should remain a
correctness and formula experiment, not be promoted on the 4.446%
multiplication-only figure.
