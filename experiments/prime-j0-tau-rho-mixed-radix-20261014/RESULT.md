# Mixed τ/ρ radix screen for variable-base j=0 multiplication

The screen constructs an exact nine-seed, six-unit digit cover for residues
modulo `τ⁴` and tests whether occasional `ρ = 2−ω` steps improve a width-four
`τ = 1−ω` expansion. The complete-cover, norm, fourth-power, and chain
reconstruction statements are checked in Lean 4.34.1. The bounded
operation-cost panel shows no useful low-search-width improvement: at beam
width eight, the mixed chain is more costly under the 10M mixed-add model
and only 6.77M lower under a 16M add model. Width 64 finds larger modeled
savings but expands about 2,800–3,100 states per scalar before any point
arithmetic. This result directs the next implementation effort away from a
general mixed τ/ρ recoder.

The supplied Xu–Yu–Han–Lu paper (local text SHA-256
`8d20aca6b52c9b6d541e858bc97fe050528f4169c7283c8e2988042b2813d28e`)
gives `τP` at `3M+3S`, `ρP` at `7M+6S`, and `3P` at `6M+4S` on a j=0
curve over a prime field. This screen sets `S=M`. A width-four τ block is
charged `21M`: `τ⁴=9ω²`, evaluated as two triplings and one cube-root
rotation. One ρ step is charged `13M`; an affine digit addition is tested at
both `10M` and `16M`. Digit-table construction, precomputation, scalar
reduction, search, and coordinate conversion are separate uncharged costs.
These assumptions make the panel an algorithmic filter, not a full-operation
performance comparison.

`screen.py` supplies exact Eisenstein arithmetic and a width-one pilot.
`window_screen.py` builds a U-invariant width-four τ table: nine seed
coefficients generate the 54 residue classes that are nondivisible by τ
modulo `τ⁴`. A τ-divisible state takes one zero-digit τ step; otherwise it
takes a width-four block. A ρ step uses one of the six unit digits or zero,
so it requires no second digit table. Every produced chain is reconstructed
exactly in `Z[ω]`. The bounded beam retains 1, 2, 4, 8, 16, or 64 states;
the 16-input pilot uses seed `20261014`, while a disjoint 64-input follow-up
uses seed `20261015`. Each coordinate is independently drawn as a signed
128-bit integer. These are coefficient-law screens; they are not GLV
representatives from a curve subgroup.

| Follow-up, 64 inputs | τ-only mean cost | Mixed mean cost | τ minus mixed | Mixed wins | Mixed states expanded |
| --- | ---: | ---: | ---: | ---: | ---: |
| Width 8, add 10M | 1216.34 | 1230.64 | −14.30 | 13/64 | 369.02 |
| Width 8, add 16M | 1434.22 | 1427.45 | 6.77 | 41/64 | 397.83 |
| Width 64, add 10M | 1216.34 | 1207.33 | 9.02 | 50/64 | 2810.63 |
| Width 64, add 16M | 1434.22 | 1401.38 | 32.84 | 62/64 | 3100.08 |

The mixed search retains the τ-only choice among its actions, but beam
pruning can discard that path; therefore a narrow beam can return a worse
chain. A runtime baseline fallback would remove a negative *curve-operation*
difference after computing both recodings, while adding the cost of that
second search. The width-one mixed pilot did show a larger modeled saving
against width-one τ, but width-four τ is a much stronger reference on the
same coefficient inputs. The paper's published 256-bit cost cannot be
compared numerically to this table because its full window method and cost
boundary differ from this deliberately simplified model.

Proof map:

| Result | Lean declaration | Exact scope | Status |
| --- | --- | --- | --- |
| τ scales Eisenstein norm by 3 | `norm_tau` | all integer coefficient pairs | checked; `propext`, `Classical.choice`, `Quot.sound` |
| ρ scales Eisenstein norm by 7 | `norm_rho` | all integer coefficient pairs | checked; same standard foundations |
| `τ⁴=9ω²` in coefficient form | `tau_fourth_power` | exact ring coordinates | checked; no axioms |
| Six unit digits cover nonzero ρ residues | `rho_unit_residue_cover` | every residue mod 7 | checked; `propext`, `Quot.sound` |
| Nine seed orbits cover nondivisible τ⁴ residues | `tau4_unit_orbit_cover` | all 81 coordinate pairs mod 9 | checked; `propext`, `Quot.sound` |
| One radix step reconstructs its quotient | `recoding_reconstruct` | arbitrary integer coefficients and remaining chain | checked; `propext` |

The proof fixes the exact residue cover and algebraic chain. A faithful Lean
bridge from these coefficient maps to the Jacobian point formulas, and a
native end-to-end variable-base evaluator, remain open. The screen does not
promote this mixed recoder to either claim.
The checked toolchain is Lean 4.34.1, commit
`5045d0056413266e57c625dcd7c365b10e377c52`; this theorem source has
SHA-256 `c25dc8b02979af93d1d813f3865f97e6a056d7175d94f69e418338acc2be2f7a`.

Reproduce the proof and screens:

```sh
/Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean experiments/prime-j0-tau-rho-mixed-radix-20261014/MixedRadix.lean
python3 experiments/prime-j0-tau-rho-mixed-radix-20261014/screen.py
python3 experiments/prime-j0-tau-rho-mixed-radix-20261014/window_screen.py
```

The JSON files retain every input, cost, action count, expansion count, and
replay status, including all pilot beam widths and both follow-up panels.
`receipt.json` hashes the exact source, Lean log, and result files. All
recorded chains reconstructed their coefficient inputs.
