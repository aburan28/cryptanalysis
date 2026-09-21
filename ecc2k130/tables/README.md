# Public precomputed pair tables

The catalog describes two synthetic ECC2K-130 pair-sum artifacts. Workers need
no AWS credentials to download published objects. S3 keys include the payload
SHA-256, and the catalog is published after every referenced file is uploaded
and anonymously readable.

Catalog URL:

```
https://ecc2k130-status-590183823895.s3.us-west-2.amazonaws.com/public/ecc2k130/synthetic-pairs/v1/catalog.json
```

| Artifact | Pair entries | Coordinate bytes | Typical free-memory budget |
| --- | ---: | ---: | ---: |
| h128 | 562,348,416 | 20,244,542,976 | 24 GB |
| h256 | 2,249,360,128 | 80,976,964,608 | 88 GB |

These budgets use decimal GB. NVIDIA memory queries return MiB and are converted
to bytes exactly. CUDA selection uses the chosen GPU's **free** memory, never a
sum across devices. On macOS, native [Metal support](../metal/README.md) uses
the device's recommended working set as an explicitly labeled planning budget,
not a global free-memory measurement. Selection includes the direction table and a configurable runtime
reserve (default 2 GiB). Selection chooses the largest fitting artifact; it is
not a measured speed ranking. The consumer must account for its own workspace
and recheck available memory when allocating GPU buffers.

## Automatic selection and download

From the repository root:

```sh
# Inspect the choice (Metal on macOS; CUDA elsewhere).
python3 ecc2k130/table_store.py select

# Download the selected artifact into a persistent worker cache.
python3 ecc2k130/table_store.py fetch --cache /workspace/tables

# Select a physical GPU index/UUID and reserve additional runtime memory.
python3 ecc2k130/table_store.py fetch --device 0 --reserve-gib 4 --cache /workspace/tables

# Explicit planning inputs, useful on a CPU host.
python3 ecc2k130/table_store.py select --free-vram-gb 24
python3 ecc2k130/table_store.py select --free-vram-gb 88
```

`CUDA_VISIBLE_DEVICES` is respected when choosing the default GPU. An empty
mask does not trigger a CUDA download. It does not mask Metal devices.
Build the native helper with `make -C ecc2k130/metal` before Metal detection.
Use `--backend cuda` or `--backend metal` to select explicitly.
A memory override is for explicit planning;
it does not prove that hardware has that memory. No fitting table returns
exit code 1 with `status: no-fitting-table`. Errors return code 2.

The shipped `catalog.json` carries the public base URL. To use a newer remote
catalog, pass `--catalog CATALOG_URL` or set `CRYPTANALYSIS_TABLE_CATALOG`.
Only HTTPS is accepted for remote downloads, with certificate verification.
On macOS Python installations lacking a configured CA bundle, use the system
bundle via `SSL_CERT_FILE=/etc/ssl/cert.pem`; do not disable certificate checks.

Downloads are streamed with bounded host memory. An interrupted `.partial`
file resumes with an exact HTTP Range request. Incorrect ranges, sizes or
SHA-256 hashes fail without promoting a partial file. Per-file locks prevent
duplicate concurrent writers. Cached complete files are hash-verified on reuse.
The cache publishes `ready.json` atomically only after all four files verify.

The client fetches `pairs.bin`, `directions.bin`, `coefficients.json`, and
sanitized `table.json`. The small catalog is checked into the repository; the
large payloads stay in public object storage.

## Programmatic consumption

`table_store.py` is a standalone standard-library module in the ECC2K runner.
It supplies a read API as well as paths suitable for a future native/GPU
consumer. It does not replace the generic C library's unrelated 64-bit tables.

```python
from pathlib import Path
from table_store import load_catalog, gpu_memory, select_for_hardware, fetch, PairTable

catalog, base_url = load_catalog()
gpu = gpu_memory()
plan = select_for_hardware(catalog, gpu, reserve_bytes=2 << 30)
if plan is None:
    raise RuntimeError('No table fits the available GPU memory')
ready = fetch(plan, base_url, Path('/workspace/tables'))
with PairTable(ready, expected_domain=catalog['domain']) as table:
    u = table.direction(h=0, k=0, eps=0)
    v = table.direction(h=1, k=0, eps=0)
    point = table.lookup(u, v)  # (x,y) as 131-bit polynomial integers; None = infinity
    a, b = table.pair_coefficients(u, v)  # point = a*P+b*Q
```

Lookups use constant host memory and 64-bit offsets. The 256-branch table has
direction IDs above 65,535 and pair indices above signed 32-bit range. Branch
count is part of the format: old direction IDs need remapping before use with
the larger table. The artifact READMEs document the formulas and coefficient
labels.

Applications should pass their expected curve/generator/target domain to the
reader. Hardware selection must not silently change an existing campaign's
walk or branch selector. The larger table embeds the smaller coefficient set,
but its direction stride changes; use `direction()` for the chosen artifact.

All tables use the known synthetic target Q=[65537]P. Catalogs are explicitly
marked `pair-sums-only`. The production Frobenius walk cannot consume them as
an acceleration without a new compatible iteration implementation, including
the intermediate branch predictor. The download/read API does not claim that
mathematical step or a GPU speedup.

## Publishing and reproducibility

```sh
python3 ecc2k130/publish_tables.py prepare
python3 ecc2k130/publish_tables.py publish \
  --bucket ecc2k130-status-590183823895 --region us-west-2 \
  --prefix public/ecc2k130/synthetic-pairs/v1
```

Publication uses the selected AWS CLI profile/environment. A new upload hashes
the complete local payload, uses multipart S3 checksums, and sets full-file SHA-256
metadata, checks remote object sizes/identities, and verifies anonymous HEAD
and first/last byte ranges. Multipart ETags are not treated as file hashes.
Existing objects are reused only when their size and recorded SHA-256 match;
a mismatch fails instead of overwriting an immutable key. A source-only
checkout can reuse an existing size/hash-matching immutable object. The catalog is
uploaded last and then read back anonymously.

The bucket grants public GetObject access only to this table prefix in
addition to its pre-existing public objects. The publisher does not alter
bucket/account policies. `upload-plan.local.json` and `publication.json` are
local records excluded from source control. Public
metadata excludes local filesystem paths, compiler commands, and credentials.

Validation:

```sh
python3 -m unittest discover -s ecc2k130/tests -p 'test_table_store.py' -v
python3 -m unittest discover -s ecc2k130/tests -p 'test_publish_tables.py' -v
```
