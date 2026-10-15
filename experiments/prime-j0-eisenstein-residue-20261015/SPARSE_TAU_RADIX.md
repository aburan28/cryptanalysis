# Sparse Eisenstein radix `127+128τ`

The radix `π=127+128τ` accelerates the table-light secp256k1 Horner path while retaining a nearby digit geometry. In a matched Tier 1 RunPod panel over **12,288 distinct frozen scalar points per arm**, it averaged **614.67 ms** online against **846.68 ms** for the earlier `334−τ` Horner path. The paired median reference/sparse ratio was **1.3772**, with a predeclared 95% bootstrap interval `[1.3659,1.3794]`. The sparse table retained **2,636,452 bytes**, 69,840 bytes more than the earlier table. All 96 arms and 48 pairs verified, the surrounding 32 A/A ratios passed, and source artifacts stayed stable.

## Algebra and exact recoding

With `τ²=3τ−3`, the pair norm is `N(a+bτ)=a²+3ab+3b²`. For `π=127+128τ`, `N(π)=114049=13·31·283`. The norm is composite, while the integer pair `(127,128)` is primitive. The quotient has the cyclic residue map `τ↦−892`, since `127+128(−892)=−114049` and `(-892)²−3(-892)+3=7·114049`. Multiplication by the radix has pair matrix

`(u,v) ↦ (127u−384v, 128u+511v)`.

Its point action is `πP=[128](P+τP)−P`: one `τ`, seven doublings, and two projective additions per Horner stage. The earlier `334−τ` point action used eight doublings and five projective additions/subtractions in the frozen native implementation. The sparse quotient of a shifted pair `(A,B)` is exactly `((511A+384B)/114049, (−128A+127B)/114049)` when both numerators divide the norm. The [screen](screen_sparse_tau_radix.py) enumerates the 57,025 signed residue indices with a bounded lift-and-round selector, then checks integral quotient steps and exact pair reconstruction for all 12,288 frozen fixture scalars. Its [receipt](sparse-tau-radix-screen.json) records 19,009 orbit seeds, maximum selected-digit norm 37,804, and 25 distinct observed terminal pairs with maximum norm 7. A conditional norm recurrence using the proved selector coordinate envelope and this exhaustive digit cap gives terminal norm below 2,130; the native constructor currently retains the older norm-5,000 terminal table.

The [hash-guarded overlay](native_sparse_tau_radix_overlay.py) changed only the radix constants, digit selector, quotient, and Horner point action in a separate copy of the frozen native source. Its [12,288-point stdout](sparse-tau-pilot-12288.stdout) reports `verified=1`, scalar phase `653.422622 ms`, preparation `275.198434 ms`, and retained table `2,636,452` bytes. This pilot was outside the Tier 1 panel and serves as exact native replay. The [native provenance archive](sparse-tau-native-provenance.tar.gz) contains both executed source trees and binaries; its SHA-256 is `0d55495b04920253bbf09593891fdf71a804b0ddd7d19c772f240924c14ffddc`.

## Paired measurement

The [manifest](tier1-sparse-tau-cpu40-manifest.json), [rules](tier1-sparse-tau-cpu40-rules.json), [launch receipt](tier1-sparse-tau-launch.json), and [auditor](analyze_tier1_sparse_tau.py) were committed before job `7b974e82dc6649b9981cf3aefcde88a6` completed. Both arms ran one pass over the same 12,288 scalar points. Rust `Instant` began after each process had prepared its own table and stopped before the independent point checks. The serial worker alternated arm order and surrounded each comparison with reference/reference controls on CPU 40. The [audit receipt](tier1-sparse-tau-cpu40-audit.json) checks all raw stdout, verification, table bytes, noise status, binary/source hashes, A/A bounds, and the paired bootstrap interval. The [raw archive](sparse-tau-tier1-raw.tar.gz) SHA-256 is `9b9fda23302dfe9f03592820c18fb23d7173dea2aee460fa5b57a8a0662b2db4`. This is a Tier 1 cloud-instance result under the recorded envelope.

| Prepared-table path | Mean online time for 12,288 points | Retained table | Paired reference/sparse median |
| --- | ---: | ---: | ---: |
| `334−τ` Horner | 846.68 ms | 2,566,612 bytes | — |
| `127+128τ` Horner | 614.67 ms | 2,636,452 bytes | 1.3772 |

## Proof map and next gate

The pinned Lean 4.34.1 module [SparseTauRadix.lean](SparseTauRadix.lean) checks the shortcut point-pair identity, exact norm, quotient residue identities, norm scaling, quotient inversion, finite exact-trace reconstruction, and mapping of a valid trace to an abstract point Horner computation. The [proof receipt](sparse-tau-lean-check.json) retains the fresh build, source hashes, and `#print axioms` output. These theorems use standard Lean foundations only. The concrete secp256k1 point-map and the Rust trace-to-Lean bridge remain open; native exact replay covers the frozen fixture. A full residue-selector optimality proof is also open and is not needed for the checked trace identity.

## Direct comparison with full prefetch

Two further panels compare the sparse path directly with the 27,429,548-byte full two-x prefetch implementation. The [cold manifest](tier1-sparse-vs-prefetch-cold-cpu40-manifest.json) and [rules](tier1-sparse-vs-prefetch-cold-cpu40-rules.json) fixed one scalar and summed process-local table preparation plus scalar multiplication for each arm. Job `6e215db536eb48428fef1ed7d40174fb` completed 96 valid arms and 48 pairs with stable artifacts and all A/A ratios inside `[0.90,1.11]`. The [independent cold audit](tier1-sparse-vs-prefetch-cold-cpu40-audit.json) reports full prefetch **3184.59 ms** mean versus sparse radix **257.57 ms** mean. The paired median full/sparse cold ratio is **12.3608**, 95% interval `[12.3259,12.3882]`. Its [raw archive](sparse-vs-prefetch-cold-tier1-raw.tar.gz) SHA-256 is `b49e418bacbd785d7e1c356c9bfa151abe072793236a61ab42265c1f453cc7fc`; the [source and binary archive](sparse-vs-prefetch-cold-native-provenance.tar.gz) SHA-256 is `ea6828b58ec03cfee0b3c6778b1c8de93b328889c17131939d107e9579b5f6bb`.

The [prepared-table manifest](tier1-sparse-vs-prefetch-online-cpu40-manifest.json) and [rules](tier1-sparse-vs-prefetch-online-cpu40-rules.json) fixed ten passes over the same 96 batches of 128 distinct scalars, with table setup outside Rust `Instant` and all **122,880** points checked after the interval. Job `f5b7ca88cbcf4d2f9175652116276b23` likewise completed 96 valid arms and 48 pairs with stable artifacts and passing A/A controls. The [independent online audit](tier1-sparse-vs-prefetch-online-cpu40-audit.json) reports full prefetch **562.36 ms** mean versus sparse radix **6048.44 ms** mean. The paired full/sparse online ratio is **0.092706**, 95% interval `[0.092583,0.093257]`, or about **10.8 times** longer for the sparse path on this prepared-table workload. Its [raw archive](sparse-vs-prefetch-online-tier1-raw.tar.gz) SHA-256 is `3692cf4129bcf1276bba3921f541958eb5c167ee86816b5a1809b58f610f1ca6`; the [source and binary archive](sparse-vs-prefetch-online-native-provenance.tar.gz) SHA-256 is `2c6a0ee8296167df359675208df796fbdf0126e0c22e176330f79faa8cbc73e9`.

| Matched workload | Full two-x prefetch mean | Sparse radix mean | Qualified paired full/sparse median |
| --- | ---: | ---: | ---: |
| One scalar, cold table | 3184.59 ms | 257.57 ms | 12.3608 |
| 122,880 outputs, prepared table | 562.36 ms | 6048.44 ms | 0.092706 |

The two rows answer different workload questions and cannot be divided into a shared per-scalar estimate. The next design gate is a checkpointed or other mixed schedule that reduces the sparse path's repeated radix actions while preserving much of its single-scalar preparation and memory advantage. Any claimed intermediate point needs its own exact replay and matched cold and prepared-table panels.
