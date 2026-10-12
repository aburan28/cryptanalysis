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
and wall measurements here are exploratory.

The [full-capacity local audit](full_audit_local/summary.json) completed the
29,900,000-state one-target stage and matched the frozen reference on every
correctness field, including the first-witness sample and operation counts.
The sidecar reduced exact record probes from 7,415,319 to 6,068,644 (18.2%).
It allocated 67,108,864 sidecar bytes and 1,342,675,968 total table bytes;
peak RSS was 3,191,373,824 bytes. The candidate's target process CPU was
39.261 s and its target-stage wall interval was 453.082 s on the contended
Mac. The [raw result](full_audit_local/raw.json),
[runner](full_audit.py), and [receipt](full_audit_local/record.json) preserve
the source/input hashes and phase accounting.

A [same-binary sparse28 baseline](full_reference_local/summary.json) also
completed the full-capacity target stage with the same exact certificate. Its
target process CPU was 38.106 s versus 39.261 s for the sidecar, a
reference/candidate ratio of 0.971. The measured target-stage wall intervals
were 349.124 s and 453.082 s, respectively, during severe Mac contention.
The [baseline runner](full_reference_audit.py) and raw receipt preserve this
negative diagnostic; the sequential local runs do not qualify as a controlled
wall-time comparison. The probe reduction therefore has no measured full-capacity
CPU win in this local check.

The full-capacity Tier 1 replay uses the same frozen target with alternating
paired orders, complete raw results, instance and cgroup receipts, and the
repository's Tier 1 promotion gate. The GitHub-hosted Linux workflow on this
branch supplies a fresh instance; the active RunPod container is occupied by
a separate solver.

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
