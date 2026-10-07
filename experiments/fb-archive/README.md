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
python3 sweeps.py export && python3 sweeps.py verify [--all-cells NAME]  # large sweeps, recipe only
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
- An explicit `--chunk-bytes 33554432` stores an oversized archive as bounded
  Git parts with `storage` `git-chunks`. A `.chunks.json` manifest and ordered
  `.part-0000`, `.part-0001`, ... files retain the original compressed bytes.
  The index's byte count and file SHA-256 still identify the complete compressed
  payload. Each part has its own size and digest; verification checks those,
  reassembly, content, record, point-set digest, and point count. Missing or
  altered parts fail verification. The current format supports at most 1 GiB
  per complete payload, 80 MiB per part, and 4,096 parts. Plain gzip/xz and the
  default S3 behavior are unchanged. The upload command includes all parts.

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

## External bases: `kerfrob`, `nbexact`, `nbstride` (`external.py`)

Three complete-DLP results built their bases outside ToyCurve and `family_basis`,
on their own fields and curves. `external.py` rebuilds each in Python and copies
the experiment's own `field` and `curve` records, so the archive's curve ID is the
one the experiment's manifests already use. Extra integer recipe parameters go in
`--extra KEY=INT` and into the archive's `recipe`, so `verify --rebuild` replays
them.

| family | experiment | recipe | curve ID | B | columns |
|---|---|---|---|--:|--:|
| `kerfrob` | `f4-gpu-20260925` | `--n 23 --l 11 --seed 0 --extra a2=0` | `EC1N23Cka0hd721efe98d4e` | 2025 | 44 |
| `kerfrob` | `f4-gpu-20260925` | `--n 23 --l 11 --seed 0 --extra a2=1` | `EC1N23Cka1h7ef98b42c1e8` | 2071 | 45 |
| `nbexact` | `hamming-ic-e2e-20260929` (6 n9 runs) | `--n 9 --l 2` | `EC1N9Ckb1h58e595b4ea93` | 36 | 2 |
| `nbstride` | `ic-candidate-catalog` complete n13 SAT | `--n 13 --l 3 --seed 87006 --extra stride=4` | `EC1N13Ckb1h15003cfcdb23` | 6 | 2 |

- `kerfrob` is the Rust suite's `build_frobenius_factor_base(kc, index)`: every
  point (both lifts, and `(0, 1)`) whose abscissa is in the kernel of the
  linearised polynomial of a top-degree irreducible factor of `x^n - 1`; `seed`
  is the factor index in ascending bitmask order (index 0 at n = 23 is
  `x^11+x^9+x^7+x^6+x^5+x+1`). Curve parameters are those of the experiment's
  manifests. Columns are signed Frobenius orbits of the cofactor projections,
  as the manifests count them.
- `nbexact` is `run_e2e_n9.py`'s base: exact normal-basis weight `w` for the
  first normal element, each rational lift projected by the cofactor.
- `nbstride` is `complete_n13_sat.py`'s base: the span of conjugates
  `0, 4, 8` of `shifted-base-geometry/audit.normal_basis(field, 87006)`, lifts in
  the order-`r` subgroup.

The two normal-basis families use `factor-base-yield-v2/engine.py`, the curve
arithmetic of those runs. Their archived `enumerated_set_sha256` equals the runs'
`point_set_sha256`, and the archived points equal the runs' `encoded_points`.
The f4-gpu results cite a Rust-convention digest under `factor_base_sha256`
(SHA-256 of sorted `"0x<x>,0x<y>"` lines), so `aliases.csv` maps each cited
digest to its archive. `verify` recomputes every alias from the archived points.
The Python rebuild reproduces both cited digests exactly. `test_external.py`
checks every link against the committed receipts, manifests and candidates. The hamming and
catalog runs cite their bases by `point_set_sha256`, which the citation guard
below also checks.

## Large sweeps: `sweeps.py`, `sweeps/`, `sweeps.csv`

A sweep runs one factor-base rule over thousands of curves, so per-base archives
with point lists are infeasible (volcano-m83 alone has 1,243,200 cells). A sweep
archive (`ic-factor-base-sweep/1`, `sweeps/<name>.json.gz`, indexed in
`sweeps.csv`) is recipe-only. It stores:

- the field record;
- every curve's `b` and EC1 curve ID, hashed from the full field and curve record
  as `fbarchive` does, with a null generator where the experiment never fixed one;
- every nested basis with the seed or rule that regenerates it, and its
  dimensions;
- the experiment's committed per-cell count files with their SHA-256.

The base of cell (curve, family, k) is `{x in span(basis[:k]) : x = 0 or
Tr(x + b/x^2) = 0}`. `B`, the point digest and the column count stay null.

| sweep | curves | families x dimensions | cells | recorded cells recounted |
|---|--:|---|--:|--:|
| `ecc2k130/research/volcano-m83` (run 08) | 6,475 | 64 x {8, 9, 10} | 1,243,200 | 1,243,200 |
| `ecc2k130-isogeny-class` | 789 | 4 x 1..16, 12 x {8, 10, 12, 14, 16} | 97,836 | 335 |
| `volcano-ic` | 457 | 1 x {10} | 457 | 457 |

`verify` rebuilds each manifest from the experiment's own committed inputs
(inventory, ground truth, `isoclass19.txt`, seeds) and checks the recorded files'
SHA-256. It then recounts sampled cells in pure Python (`--cells`, default 40)
against the recorded counts, or every recorded cell with `--all-cells NAME`.
Every recorded cell of all three sweeps recounts exactly; volcano-m83's 1.24M take
about a minute.

Gaps:
- The isogeny-class per-cell counts (`raw_counts*.json`) were never committed.
  Its recorded cells are the 263 canon k = 16 counts implied by the 4-decimal
  `ic_density_z_k16` column (exact), E0's 60 replicate z-scores, and 12 Codex
  fingerprints.
- Its null curves R/S are regenerated from their seeds. The S set's
  order-rejection step needs point counts and is not re-checked.
- The volcano-ic tau-closure and normal-basis E0 variants are not included.

## Citation guard: `refs.py`, `unarchived.csv`, `backfill.py`

`refs.py check` (CI workflow `fb-refs`) reads every committed JSON / JSONL
result under `experiments/` and `ecc2k130/research/`, including `.gz` and `.xz`,
and collects each `factor_base_sha256` and each point-set digest
(`point_set_sha256`, `enumerated_set_sha256`, `factor_base_point_set_sha256`,
`base_digest`: SHA-256 of the canonical sorted `[[x, y], ...]` list, the
archive's `enumerated_set_sha256` convention). Every cited digest must be the
`factor_base_sha256` or `enumerated_set_sha256` of a row of `index.csv`, a
`cited_sha256` of `aliases.csv` whose archive is indexed, or a row of
`unarchived.csv`, the closed list of known, not-yet-archived
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
reproduce: a prime-field base (`bielliptic-quartic`) and a rational "fraction"
base (`homogeneous-fraction`), and three `ic-candidate-catalog/profiles.json`
design-profile bases cited by point-set digest: the n = 19 shifted union
(`649f7b…`), the n = 131 degree-7 sample (`9e160f…`) and the n = 131 ONB
weight-2 base (`fca949…`, hashed as ONB coordinate masks, a different encoding).
None of them is a complete-DLP result. The `f4-gpu-20260925` bases were cleared
through `external.py` and `aliases.csv`. Results that record a base under another
key (`base_sha256`, whose convention differs between experiments, or inline
point lists) or record only counts are not seen by the guard.

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
