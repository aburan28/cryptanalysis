# Radix-14 rotation cache under 32 MiB

The implementation precomputes two-x rotation data for ten of its fourteen digit rows while retaining 33,318,020 bytes, below the fixed 33,554,432-byte table cap. The frozen seven-row parity cache retains 31,133,444 bytes. Both paths reproduced 12,288 independently checked secp256k1 scalar points on the unseen evaluation fixture. The [serial Tier 1 comparison](tier1-cache10-cpu40-manifest.json) and its [acceptance rules](tier1-cache10-cpu40-rules.json) recorded 96 valid arms and 48 valid pairs. Two adjacent A/A controls exceeded the predeclared `[0.90,1.11]` interval, so the aggregate timing comparison remains unknown.

## Choice of cache entries

[Training input](rotation-cache-training-20000.json) contains 20,000 independent SHAKE256-derived scalars, with a distinct derivation domain from the 12,288-scalar evaluation fixture. The [profile overlays](native_rotation_profile_overlay.py), [per-seed counter overlay](native_seed_profile_overlay.py), and [raw histogram overlay](native_seed_hist_overlay.py) instrumented the frozen radix-14 native source. The [histograms](seed-hist-training.json.gz) and [evaluation histograms](seed-hist-evaluation.json.gz) retain the raw row/seed counts. The [transfer analysis](rotation-seed-transfer-audit.json) and its [script](analyze_rotation_seed_transfer.py) measure training-to-evaluation stability.

Across the fourteen digit rows, the mean Pearson correlation between per-seed training and evaluation counts was 0.003705. A top-1,000 seed subset chosen separately in each row from the training sample covered 16.6972% of training selections but 4.4789% of evaluation selections; a uniform 1,000-of-22,756 subset covers 4.3944%. The observed hot seeds therefore did not transfer usefully to the held-out fixture. The terminal row has a different seed distribution and is kept as ordinary affine entries in both candidates.

The ten-row [overlay](native_cache10_overlay.py) chooses digit rows `0,1,3,4,6,7,9,10,12,13`, without consulting evaluation scalars. The seven-row [reference overlay](native_cache_uniform_overlay.py) exposes the existing even-row cache under the uniform fixture. Both select the same precomputed affine points and use the same affine layer reduction. The change affects only which digit rows store the two-x orbit form. The reference and candidate binaries, source hashes, fixture, and exact replay outputs are frozen in the [native provenance archive](cache10-native-provenance.tar.gz), SHA-256 `0320bddb984f3f3afc958d0d2e2467779596ebc3516f612f07ded96cf25ff6da`. The profiler source snapshots and binaries are in the [profile provenance archive](rotation-cache-profile-native-provenance.tar.gz), SHA-256 `2ba956e7b33a20127905267b8d287cb77433c7b294df0bb19e865fd92d983c87`.

## Measurement boundary

The RunPod worker runs one job at a time. The manifest pins the cloud instance, CPU 40, source and executable artifacts, the 12,288-scalar fixture, sixteen alternating reference/candidate pairs, and adjacent A/A controls. Rust `Instant` times 96 consecutive 128-scalar batches after fixture loading and table construction. Every output is checked against independent binary multiplication outside the timed interval. Preparation time and retained table bytes are reported separately. The tier is cloud-instance Tier 1; physical-host isolation is unobserved. The workload is batch scalar multiplication.


## Serial panel and interpretation

The completed job `e0d10d9a14e4406684212690eb680518` preserved all [raw arms and pair records](cache10-tier1-raw.tar.gz), SHA-256 `0f68e3e2c1c54ba00013b803b6a135b484b9c3e1742286650952603f0e087f47`. The [independent audit](tier1-cache10-cpu40-audit.json) checked the frozen manifest, source and binary hashes, exact replay outputs, all 96 arm records, and all 48 pairs. The runner reported stable artifacts and 48 valid pairs.

| Tier 1 uniform scalar stream; 12,288 outputs per arm | Seven-row cache | Ten-row cache |
| --- | ---: | ---: |
| Retained table bytes | 31,133,444 | 33,318,020 |
| Mean timed 12,288-scalar interval | 67.807406 ms | 65.714195 ms |

The descriptive median paired seven-row/ten-row ratio was `1.028614`; its paired bootstrap 95% interval was `[1.014163,1.046736]`. The A/A ratios at repeat 1 after comparison and repeat 2 before comparison were `1.203446` and `1.201942`, outside `[0.90,1.11]`. Under the frozen gate the qualified ratio is `null` and the aggregate status is `unknown_after_tier_gate`. These failed controls remain in the result; a further timing panel needs a newly frozen environment and manifest.
