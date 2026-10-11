# Sidecar singleton tag for the N83 E-1 root index

The sparse28 root index now has an optional byte of fingerprint for each
occupied bucket. Its existing 32-bit offset stores as many low key bits as
the record count permits. For a singleton bucket, a lookup reads the sidecar
byte only after those low bits match, then loads the exact 16-byte record
only if both checks pass. Multi-record buckets keep their exact binary search.
This preserves the first-witness rule and the full key comparison.

At the frozen 29,900,000-state capacity, the 32-bit offsets have five tag
bits. The sidecar tests eight more bits and stores one byte per occupied
bucket: about 51 MiB of data at the previously measured 53.6-million-bucket
count. Vector capacity may reserve 64 MiB. The output records the allocated
capacity and the number of exact record probes.
The stage remains a proposal with `candidate_id: null`; its complete IC
pipeline is specified separately by the candidate catalog contract.

## Frozen screen

The release source passed eight tests, including exact hit/miss and duplicate
witness parity plus a same-bucket singleton miss that the sidecar rejects
before a record probe. The [2-million-state screen](screen_2m/summary.json)
completed in split/sidecar/sidecar/split order on the same public target.
All 22 parity fields matched, including operation counts, lookup witnesses,
and bounded-stage status.

| Order | Directory | Target record probes | Target CPU (s) | Table allocation (MiB) |
| --- | --- | ---: | ---: | ---: |
| 1 | split | 2,995 | 1.904 | 125 |
| 2 | sidecar | 2,087 | 1.832 | 129 |
| 3 | sidecar | 2,087 | 1.777 | 129 |
| 4 | split | 2,995 | 1.999 | 125 |

The screen establishes exact behavior and a lower record-probe count. Mac CPU
and wall measurements here are exploratory. The full-capacity Tier 1 replay
must use the frozen 29,900,000-state one-target input, alternating paired
orders, complete raw results, host and cgroup receipts, and the repository's
Tier 1 promotion gate. The active RunPod container is occupied by a separate
solver, so this replay awaits an idle instance.

## Reproduction

The Cargo dependency points to the pinned public source restored by the
adjacent sparse28 capacity experiment. From this directory:

```sh
python3 ../packed_index_e1_sparse28_capacity_20261011/restore_crypto_source.py
export CARGO_TARGET_DIR=/workspace/build/n83-e1-tagbyte
export CARGO_NET_OFFLINE=true
export NATIVE_S3_SOURCE_SHA256="$(sha256sum native_packed_index.rs | cut -d ' ' -f 1)"
export NATIVE_S3_BUILD_MANIFEST_SHA256="$(sha256sum Cargo.toml | cut -d ' ' -f 1)"
cargo test --release --locked
cargo build --release --locked
python3 screen.py --binary "$CARGO_TARGET_DIR/release/native_packed_index_tagbyte" \
  --output-dir /workspace/results/n83-e1-tagbyte-screen
```

On an idle Linux instance, validate the checked-in receipts and create the
Tier 1 manifest with its real allocation receipt and pinned execution CPU:

```sh
python3 verify_screen.py
python3 make_tier1_manifest.py \
  --workdir /workspace/cryptanalysis \
  --binary "$CARGO_TARGET_DIR/release/native_packed_index_tagbyte" \
  --cpus "$N83_E1_CPU_SET" --execution-cpu "$N83_E1_CPU" \
  --provider runpod --instance-id "$N83_E1_INSTANCE_ID" \
  --allocation-receipt "$N83_E1_RECEIPT" \
  --output /workspace/results/n83-e1-tagbyte-tier1-manifest.json
python3 /workspace/cryptanalysis/scripts/isolated_bench.py run \
  /workspace/results/n83-e1-tagbyte-tier1-manifest.json
```

The manifest generator also runs the parent capacity verifier and checks the
one-target full-capacity certificate. The isolated runner retains its own
preflight, raw pair results, cgroup counters, and bootstrap interval.
