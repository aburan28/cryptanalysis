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

## Streaming point and orbit metadata shards

`orbit_shards.py` provides a separate `ic-factor-base-shards/1` format for
enumerated bases too large for one JSON object. A producer streams **strictly
sorted** `(x, y)` rows; the writer retains at most `--shard-records` rows
per compressed shard and builds a content-addressed manifest. Its
`enumerated_set_sha256` is computed incrementally using the existing
canonical sorted-point-list encoding, so the final count and digest must
match the existing `factor_base` record. A recipe-only base has unknown
`B` and digest and cannot claim a completed point archive.

Input `--record` is a small JSON object containing the existing `field`,
`curve`, and `factor_base` records. Input `--rows` is JSONL or `-` for
standard input. Each row has exactly these seven fields:

```json
{"point":[12,34],"subgroup_projection":null,"orbit_key":null,"frobenius_phase":null,"sign":null,"column_id":null,"column_coefficient":null}
```

The coordinates use the field record's unsigned integer encoding.
`orbit_key` names an implementation-defined projected quotient key;
`frobenius_phase` is an exponent from `0` to `n-1`;
`sign` is `-1` or `1`. The column ID and coefficient must both be
present or both null. The archive verifies **structure, hashes, order, and
agreement with the enumerated point set declared by the existing digest**.
It does **not** prove subgroup projection, orbit equivalence, phase,
coefficient, or usefulness for point decomposition; manifests explicitly
carry `annotations_verified: false`. Publish a separate mathematical
verification receipt before using these annotations as relation columns.

```bash
python3 orbit_shards.py ingest --record base-record.json --rows sorted-points.jsonl \
    --out /data/factor-bases --shard-records 100000
python3 orbit_shards.py verify /data/factor-bases/manifests/<sha256>.json
```

The producer may also call `write_shards(root, record, row_iterator)`
directly without materializing its point set. Each shard stores canonical
JSONL in deterministic gzip, with compressed and uncompressed SHA-256,
byte count, record count, and first/last point in the manifest. The
content-addressed manifest includes the complete base record and its
original `factor_base_sha256`; it is independent of absolute paths and
measurement run IDs. Keep `candidate_id`, `workload_id`, and `run_id`
in a separate benchmark table under the AGENTS.md measurement contract.
This format is a storage substrate for a future nonlinear orbit-union
generator, not evidence that such a base improves relation yield at N131.
