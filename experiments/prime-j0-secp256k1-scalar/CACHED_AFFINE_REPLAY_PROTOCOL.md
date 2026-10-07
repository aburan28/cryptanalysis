# Affine control on the frozen cached-projective panel

The 64 inputs in `cached-projective-result.json` were frozen before
the cached projective run. Freeze `replay_cached_affine.py` and this
protocol before replaying those same inputs through the optimized
all-affine seed path. This is an additional paired control on an
already observed panel, not a new prospective panel. The Sage launcher
runtime receipt must be saved before execution.

For every case, derive the exact base and scalar from the saved hex
inputs. Rebuild and independently verify all nine optimized seed
points, batch-normalize eight with one inversion, prepare the unit
orbits, evaluate the same short representative and width-four digits,
and independently check the output against Sage and the saved point.
Require identical τ-step, pair, and digit-addition counts. Save the
affine source counts, the cached projective counts from the frozen
record, and the paired `M`, `S`, and `M+S` threshold for one extra
preparation inversion. The common final output inversion is excluded
from both arms and cancels.

The threshold is an arithmetic-model result. Do not infer a CPU ratio
without a native complete-operation run and host-level isolation. Both
cached readdition and batch inversion have prior art; no academic
novelty claim follows from this replay.
