# ECC2K83 explicit-base frontier: preregistered feasibility screen

This follows the [ordinary query campaign](ordinary-evidence-20260928/README.md).
Its (n=83), three-summand base of 52 projected subgroup points has a
uniform-query coverage upper bound of (6.16\times10^{-20}). Further trials
against that fixed base cannot test the 2× cost per independent row goal.

**Question:** Can a point-by-point enumerable, subgroup-valid (n=83) base
reach even the *necessary counting bound* for 1% coverage of uniform
nonidentity subgroup queries at three, four, or five summands? The comparison
is between summand counts on an identical curve and actual factor-base points.
The base and generator remain separate from a solver or relation collector.

## Frozen design and limits

* Curve (y^2+xy=x^3+1), binary polynomial field representations and exact
  curve/subgroup orders come from `ordinary-evidence-20260928/n13.json` and
  `n83.json`. Validate the existing full-factorization Lucas certificates.
* Construct (F_l=\{P:x(P)\in\operatorname{span}(1,z,\ldots,z^{l-1})\}\) for
  ((n,l)=(13,5),(83,6),(83,12),(83,16)). The first two are exact control
  bases from the previous frozen run. Project each original point via ([4]),
  remove identity and identify signs only for matrix columns. Report actual
  distinct subgroup point count (B), signed columns, and checksums.
* One serial C++ enumerator, `g++ -O3`, 120-second watchdog and 512 MiB
  address-space limit per case. Preserve every raw point and projection,
  stdout/stderr, compiler receipt, host, source hashes and checksums.
  Compiler time is an environment cost; enumerate and audit time are reported
  separately and together as base preparation. Compression is archival.
* C++ checks each lift and projected point is on the curve. Independently
  check all original x-values in both controls and 32 or more frozen sample
  x-values in each larger case using `gf2n.py`, including exact signed
  projection and ([r]([4]P)=O\). Group-order proof implies this subgroup
  condition for every projected point; the larger-point sample checks
  implementation agreement. Any wrong control, corrupt member, timeout or
  failed verification has no accepted (B).
* Counting bound only: for each (m\in\{3,4,5\}\),
  (\Pr(\text{uniform target has a decomposition})\le
  \min(1,(B+1)^m/(r-1))\), where the extra element allows the cofactor-zero
  image. Compute exact integer numerator, denominator and minimal (B)
  for the 1% **upper bound** to become possible. This is a necessary
  feasibility screen, not a measured yield, lower bound or solver-speed claim.

**Success for this screen:** a case with a verified exact base and a bound at
least 1% for (m=5), while retaining measured construction cost. Then a new
frozen experiment must find ordinary relations and independently verify rank
on that same base, with a compiled same-base direct control. No cost per useful
row is finite in this base-only screen. If the enumerator times out or the
base stays too small, retain the negative result and redirect to a different
base construction or encoding. `n=131` and full one-target DLP remain unrun.

```sh
python -m unittest discover -s experiments/pdp-scaling -p test_explicit_base_frontier.py -v
python experiments/pdp-scaling/explicit_base_frontier.py freeze MANIFEST.json
python experiments/pdp-scaling/explicit_base_frontier.py run MANIFEST.json NEW_OUTPUT_DIRECTORY
```
