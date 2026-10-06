# Degree-263 transport cost on frozen ECC2K-130 points

This retrospective, exploratory stage experiment measures the target-dependent
cost of the exact degree-263 map and its subgroup inverse. It uses the public
point-only workload and base controls frozen in parent PR #305; no point,
factor base, or solver is selected from the timings. The source and descendant
are the exact `EC1` models and verified route in that workload.

Construct the forward and dual isogenies from the pinned kernel polynomials
using the checked repository Sage launcher. Save `sage --runtime-info` before
the run. Keep input loading, field and map construction, point decoding, and
independent equality checks outside the timed map calls. Time the following
operations once per point, in frozen order:

1. Forward transport of public source targets 0–63. Target 0 is the primary
   one-target workload; the other 63 are dormant controls, used only for a
   descriptive cost distribution.
2. Inverse transport of their descendant images by the verified dual,
   codomain isomorphism, orientation sign, and multiplication by
   `263^(-1) mod r`.
3. Forward transport of the 64 archived source-base control points.
4. Inverse transport of the 64 archived descendant-native base controls.

Check every output against the independently frozen counterpart. Preserve
per-call nanoseconds, map setup wall time, exact input/source/runtime hashes,
architecture, and peak RSS. A failed comparison invalidates the receipt.
Report medians and ranges as unisolated-host diagnostics only. The primary
target's forward and inverse map times are transport stage observations, not
an IC online interval. Do not multiply a 64-point average by the full base
size and call it a measured build cost. No PDP, relation, rank, matrix, DLP,
rho, or speedup result is produced here; `candidate_id` remains null.

This stage answers which direction of the route is computationally cheap
enough to include in a future four-policy comparison. The transported-source
and source policies, and likewise the native-descendant and pullback policies,
have identical mathematical sum membership under the subgroup isomorphism;
their implementation costs still require measurement.
