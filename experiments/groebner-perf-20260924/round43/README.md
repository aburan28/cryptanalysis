# Independently checked partial-affine residual certificates

An affine consequence can restrict a Boolean residual system even when its
rank is too small to determine a unique assignment. This experiment retains
original-equation witnesses, independently reconstructs their affine
consequences, and enumerates every assignment in the resulting affine space.
Every returned root is checked against the original residual equations.

The producer and checker are separate portable C++ libraries. Contexts reuse
only monomial layouts; coefficients and witnesses are fresh. The checker
accepts no producer rank, pivots, roots or intermediate elimination table.
Dependent or zero witnesses cannot increase the independently recomputed
rank. Empty certificates use complete enumeration. Failed work, assignment
or capacity limits return no partial root set and preserve output buffers.

The current bounds are 1–10 residual variables and 1–128 equations, with
quadratic original ANFs. This is an isolated residual primitive: it does not
change solver dispatch or certify a complete global Gröbner basis. The
unmodified surrounding query still requires its own basis and curve checks.
No GPU implementation, measured latency gain, full IC result or new general
asymptotic algorithm is claimed here.

## Reproduce correctness

No Sage, NumPy or GPU dependency is needed. From the repository root:

```sh
python3 experiments/groebner-perf-20260924/round43/build.py
python3 experiments/groebner-perf-20260924/round43/validate_native.py
python3 experiments/groebner-perf-20260924/round43/audit.py
```

`CXX` selects the current platform compiler. The build produces separate
optimized and UBSan producer/checker libraries and records source hashes,
binary hashes, compiler commands and host architecture. Validation refuses
to overwrite an existing report. Its default outputs are under `build/`;
`--output` selects a separate report location.

The frozen corpus has 17,258 systems: 16,656 exhaustive one-, two- and
three-variable polynomial pairs, 400 randomized width controls, 16 planted
ten-variable structural controls, 162 unchanged real residuals and 24
high-word controls. Both builds must pass, yielding 34,516 system runs and
29 guard groups per build. Witness identities, independently computed rank,
complete roots, reordered/duplicated/empty witnesses, failure budgets,
fresh inputs, concurrent reuse and closed handles are checked. The separate
audit regenerates the corpus and recomputes every certificate and complete
root set from original equations.

The 162 branch identifiers are frozen in `fixtures/frozen-controls.json`.
Their original ANFs remain in the hash-bound round40 fixture. Structural
controls are correctness fixtures; their rank or root counts are not natural
relation-yield estimates. The work counter is a bounded implementation
counter, not a complete CPU or IC operation count. Sorting comparison counts
can differ between standard libraries even when outputs are identical.

The initial physical Apple M4 Pro prototype passed the complete corpus in
optimized and UBSan builds. The checked-in package must be rebuilt and
validated on each claimed platform; hosted Linux/macOS correctness is not
a physical-device speed measurement. CI retains reports, audits and native
binaries so their recorded identities can be verified.

See [DESIGN.md](DESIGN.md) for soundness and bounded residual costs,
[INTEGRATION.md](INTEGRATION.md) for full-query and memory requirements, and
[PRIOR_ART.md](PRIOR_ART.md) for the limits of the algorithmic claim.
