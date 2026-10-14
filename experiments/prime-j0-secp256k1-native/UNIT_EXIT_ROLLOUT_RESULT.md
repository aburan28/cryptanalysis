# Unit-assisted degree-seven exits for linked scalar recoding

A one-step policy improvement over the linked 2/τ/ρ/conjugate-ρ
recoder lowers its charged field-operation count by **17,551 M+S units
(1.247%) across 1,088 frozen secp256k1 scalar cases** when only new
unit-assisted exits are admitted. The broader legal-action rollout lowers
the count by 19,166 units (1.362%). Every output digit stream reconstructs
the original Eisenstein representative exactly. The baseline count matches
the native linked-tail replay on all five panels.

## Recoding rule

At a high-norm state `s=(a,b,pending_τ)`, let `V(s)` be the charged cost
of finishing with the existing greedy recoder and its exact norm-4096 tail.
The unit policy evaluates the greedy action and the legal exits that first
subtract an Eisenstein unit and then divide exactly by `2`, `ρ=1+τ`,
or `4-τ`. It selects the action minimizing

`immediate_M_plus_S + V(successor)`, keeping the greedy action on a tie.

The broader policy also considers the other legal zero-digit radices and
the usual width-four `τ` digit. After taking an action, each policy
recomputes the choice at the next state. The norm-4096 tail is unchanged.
The unit digit uses the already prepared base-point orbit, so it adds no
seed-preparation cost. The full charged source total includes the linked
68-unit seed preparation and 57-unit common-Z alignment per scalar.
As in the matched native source model, both arms omit the one final
common-Z restoration multiplication. Integer recoding, memory traffic,
affine conversion, and output checking are outside this M+S count.

The greedy action is always among the choices. Since each admitted
high-norm action decreases the Eisenstein norm, induction on that norm
shows that repeating this one-step improvement cannot exceed the greedy
source cost for any state. The candidate stream is also finite: a unit
has norm 1, so its 2- or degree-seven quotient contracts the norm above
4096 more strongly than the width-four `τ` digit bound in
`LINKED_MIXED_TERMINATION.md`. The same 222-action upper bound applies.

## Frozen source-operation screen

`unit_exit_rollout_screen.py` imports the linked digit atlas and exact tail
generator, uses the fixture's frozen short representative, reconstructs
every action stream, and checks the native greedy aggregate for each full
panel. The arithmetic counts are deterministic; the code ran on an ordinary
local host and reports no CPU speedup.

| Panel | Cases | Native-matched greedy M+S | Unit exits M+S | Unit saving | Unit wins / ties | All actions M+S |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Design | 64 | 82,772 | 81,625 | 1,147 | 61 / 3 | 81,535 |
| Fresh | 256 | 330,994 | 326,991 | 4,003 | 246 / 10 | 326,603 |
| Coset | 256 | 331,038 | 327,156 | 3,882 | 241 / 15 | 326,698 |
| Linked fresh | 256 | 330,962 | 326,697 | 4,265 | 246 / 10 | 326,386 |
| Zero-τ | 256 | 331,564 | 327,310 | 4,254 | 248 / 8 | 326,942 |
| **Total** | **1,088** | **1,407,330** | **1,389,779** | **17,551** | **1,042 / 46** | **1,388,164** |

The unit policy took 2,616 unit-assisted exits across the five panels.
Its largest observed stream had 156 actions, within the proved bound.
The broader policy improved 1,052 cases and tied 36. The exact tail audit
covered 29,688 states and 138,240 transitions, and the frozen linked tail
SHA-256 remained
`56c1e92b44ed14ce5b807c33159bf1f46850f1ce8eb0aff8582c961ce5fc8fd7`.

The rollout evaluates the old policy from many alternate successors:
approximately 1.8 million memoized greedy states were visited for each
256-case panel. That is search effort, not field arithmetic, and must be
charged in a native end-to-end implementation. The next implementation
step is a bounded or precomputed decision policy that preserves most of
the source saving with much less integer recoding work, followed by native
point replay and the isolated paired CPU measurement.

Reproduce a panel from this directory with:

```sh
python3 unit_exit_rollout_screen.py --fixture fresh-fixture.json
```
