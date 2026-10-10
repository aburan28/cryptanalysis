# Degree-263 exceptional-input confirmation

This run checks the catalog's degree-263 route status against the already
archived forward and dual map controls. The route is
`IW1E263d1hadee4e69fa3d` on the ECC2K-130 subgroup over `GF(2^131)`.
The [frozen input record](FROZEN.json) fixes the source commit, map and
receipt hashes, 180-second external wall cap, and expected kernel counts.
This is a confirmation of map correctness and catalog status; elapsed time
is recorded for reproducibility but is not a comparative performance result.

Run the static route-manifest verifier, then the repository's checked Sage
launcher. Save its runtime information before the Sage arithmetic starts.
The replay must send infinity, the rational order-two point, and all 262
nonzero points in each geometric kernel to the specified codomain images;
it must check ordinary-point agreement and the oriented dual composition.
Preserve raw stdout, stderr, exit status, wall time, and receipt hashes even
if a step fails. The replay uses an existing public fixture and does not
select a new target.

From this checkout, execute once:

```sh
python3 experiments/ecc2k130-263-exceptional-audit-20261010/run.py
python3 experiments/ecc2k130-263-exceptional-audit-20261010/audit.py
```

`audit.py` requires byte hashes of the frozen sources and compares every
semantic field of the new checked-Sage receipt to the archived receipt. It
excludes only the four elapsed-time fields from that equality, checks the
forward and reverse kernel counts, and verifies the static registry binding.
If the replay differs, retain the raw run and leave the catalog status open.
If it passes, replace the catalog's stale exceptional-transport “next gate”
with the verified route and keep the equal-base PDP/rank comparison as the
next unsatisfied stage. The existing manifest's `candidate_id` remains null.
