# Factor-base archive

Reproducible, content-addressed copies of the factor bases used by the IC
experiments: the full AGENTS.md `factor_base` record, the exact `field` and
`curve` records it belongs to, and (when enumerated) the sorted usable point set
whose SHA-256 is the record's `enumerated_set_sha256`.

```bash
python3 fbarchive.py export --n 19 --family geomtrace --l 5              # one toy base (pdpkernel.c)
python3 fbarchive.py export-suite --suite full                           # every ic-bench base
python3 fbarchive.py export --n 131 --family geomtraceu --l 12           # ECC2K-130, pure Python
python3 fbarchive.py export --n 131 --family prefix --l 28 --no-points   # recipe and basis only
python3 fbarchive.py verify [--rebuild [--rebuild-max-points 300]]      # check the index
python3 fbarchive.py upload [--dry-run] [--require]                     # to $IC_ARCHIVE_S3_URI
python3 -m pytest -q .
```

## Layout

- `bases/<curve-id>/<family>-l<l>-s<seed>-<fb-digest12>.json.gz`: a deterministic
  gzip (`mtime` 0, level 9) of sorted-key compact JSON. `--codec xz` uses lzma
  instead. Both codecs are stdlib-only.
- `index.csv` has one row per archive. It records the record digest, the curve ID, the
  recipe, `fb_points` (B), the geometric point count, the effective (folded)
  column count, the strict `<G>` count, the quotient rule, whether points are
  included, the storage location, the byte size, and the SHA-256 of the compressed file,
  of the JSON content and of the point set.
- `large/`: archives above `--max-git-bytes` (1 MiB) get `storage` `s3`. They
  are git-ignored and must be uploaded; `verify` skips them when absent.

`verify` rechecks every digest and count, and flags files that are not in the index.
`--rebuild` also regenerates each base from its recipe and requires byte-identical
content. CI rebuilds everything up to 300 points; a full rebuild takes a few
minutes, most of it the N131 `l = 12` bases.

## Builders

- `n <= 63` uses `factor_base.FactorBase` (pdpkernel.c), so the archived
  record is exactly the one hashed into ic-bench candidate manifests.
- `n = 131` uses `purepy.py`, a pure-Python field and curve on the ECC2K-130
  challenge generator (`EC1N131Ckb1h856fd29cb4b4`, polynomial basis
  `z^131 + z^13 + z^2 + z + 1`, h = 4). The subspace comes from the same
  `factor_base.family_basis`. The usable points are those outside `E[4]`, and
  the columns are the classes `{±P + T : T in E[4]}`, which is the same rule as
  the toy bases. The tests check that the pure-Python builder reproduces
  `FactorBase.record()` on toy curves. Strict `<G>` membership (`[r]P = O`) is
  counted only up to `--strict-limit` points.
- `--no-points` stores the basis and recipe only. B, the column count and the
  point-set digest are then **null (unknown)**, not zero, and no `fb<B>` label may be
  formed from such a row.

## Families

These are the families of `pdp-degree-heuristics/factor_base.py`. `geomtrace` is kept
byte-for-byte because recorded receipts replay it. It draws the scale `c` as an
*integer* sum of kernel vectors and rejects bases outside ker(Tr). Each draw
therefore succeeds with probability about `2^-l`, which is fine for the toy
suites but does not finish at N131 beyond `l = 12`. `geomtraceu` samples the same
subspace law with `c` uniform on the kernel (an XOR of a random subset). It
is a different family with different digests; use it for large `l`.

## `nbweight`: the normal-basis weight base

`--family nbweight --l w` archives `{P : 1 <= HW(x(P)) <= w}`, the Hamming weight
taken in the normal basis of `ecc2k130/runner/codegen/curves.NormalView` (normal
element seeded by `n`). It is Frobenius stable but not a subspace, so `basis` and
`nominal_dimension` are null and `l` is `w`. It is built through the same
`NormalView` and `CurvePb` that `indexcalc.factorBase` and
`experiments/frobenius-quotient-m4/ladder.py` use, and carries its own field and
curve records: `NormalView` picks its own modulus, which is not always
`ToyCurve`'s (n = 13), and `ToyCurve` refuses n where r^2 divides #E (n = 11).
No subgroup projection is applied, matching how the ladder uses it, so subgroup
order, generator and strict counts are null. Columns are x-classes under sign
and Frobenius.

## Citation guard: `refs.py`, `unarchived.csv`, `backfill.py`

`refs.py check` (CI workflow `fb-refs`) reads every committed JSON / JSONL
result under `experiments/` and `ecc2k130/research/`, including `.gz` and `.xz`,
and collects each `factor_base_sha256`. Every cited digest must be a row of
`index.csv` or of `unarchived.csv`, the closed list of known, not-yet-archived
bases. The list is exact both ways: a new unarchived citation fails, and so does
a debt row that has since been archived or is no longer cited. It can only
shrink. `refs.py report` prints the per-experiment counts.

`backfill.py <experiment-dir> ...` archives cited bases from the recipe recorded
beside each citation (a `cell` or `recipe` object with n, family, l, seed). It
stores a base only when the rebuilt `factor_base_sha256` equals the cited one,
and reports anything it cannot rebuild. It backfilled 2,466 bases from
`fb-search` (scans and trace-equation runs) and `pdp-degree-heuristics`
(per-attempt profiling), all of them byte-exact.

The remaining debt (`unarchived.csv`) is bases that no builder here can
reproduce: a prime-field base (`bielliptic-quartic`), the Frobenius-invariant
Rust-built bases on the `Cka0`/`Cka1` curves (`f4-gpu-20260925`) and a rational
"fraction" base (`homogeneous-fraction`). Results that record a base under
another key (`point_set_sha256`, `base_sha256`, inline point lists) or record
only counts are not seen by the guard; see the audit in the PR that added it.

## Linking experiment cells: `ps1.py`

`ps1.cell_manifest(n, family, l, pdp)` returns an experiment cell's archive row
(curve ID, `factor_base_sha256`, path) and its `PS1N<n>C<tag>fb<B>PDP<m><solver>h<12hex>`
label, hashing the archived factor-base digest with the experiment's
point-decomposition record. `experiments/frobenius-quotient-m4` and
`experiments/linearized-half-decomposition` write theirs to
`results/factor_bases.json` (`python3 fb_manifest.py`), and their tests rebuild
each base with the experiment's own code and compare it with the archive.

## Existing N131 artifacts

The catalog's N131 proposals (`ic-candidate-catalog/README.md`, `profiles.json`)
cite `experiments/nonfrobenius-ic/results/ecc2k130-run01.json` for the `fb26`
polynomial-subspace base. That directory is not in this tree, so its point
list is not archived here. The prefix bases above are `span{1, z, ..., z^(l-1)}`
with the `cofactor_projection` policy. They are not claimed to equal that
artifact or the `n131_poly_d*` proposals. Their B values are the counts at
`l = 8, 12`, and they are unknown above that. None of these rows is an `IC1` candidate: no
N131 pipeline here has run a complete DLP.

## S3

`upload` reads the destination from `IC_ARCHIVE_S3_URI` (`s3://bucket/prefix`)
and credentials from the standard AWS chain, using boto3 or else the `aws` CLI.
Nothing is hardcoded. Without a URI or credentials, it prints why and exits 0;
`--require` makes that exit 1. Objects go to
`<prefix>/factor-bases/<curve-id>/<file>` with `sha256` metadata, and unchanged
objects are skipped when boto3 can read that metadata. CI uploads only on pushes
where `IC_ARCHIVE_S3_URI` and AWS secrets are configured.
