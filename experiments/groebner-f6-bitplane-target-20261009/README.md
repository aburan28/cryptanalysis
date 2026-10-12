# Exact reusable F6 boundary bitplanes

For the four-summand S3 chain, the cached static elimination leaves a
12-variable separator. This opt-in kernel enumerates its 4,096 boundary
assignments once at setup, storing the static feasibility bitset and exact
Boolean truth planes for the target-zero ANF rows and each target-bit delta.
For a fresh target, it XORs only the selected deltas, intersects every row's
zero plane with the static bitset, reconstructs a static witness, and checks
the original equations and curve point. It stores target-independent equation
responses, not target solutions or scalar answers.

The applicability gate requires at most 16 separator variables, at most 31
target bits, a field-width set of affine target equations, and the declared
state and plane-memory caps. Larger or differently structured systems remain
on the exact packed-ANF path. A dense cross-link that makes the separator
grow with the whole system removes this kernel's advantage. Setup and its
template-evaluation count are recorded separately from fresh-target query
time. The candidate is an exact bounded-width specialization, not a general
asymptotic improvement over F4 or F5.

Validation includes exhaustive random Boolean systems in optimized and UBSan
builds, boundary-rejection controls, all 512 frozen S3 target abscissae, and a
paired complete-query panel. Source and protocol are committed before builds
or timing. The local CPU panel is exploratory until an isolated-host receipt
qualifies it. Default routing remains unchanged.
