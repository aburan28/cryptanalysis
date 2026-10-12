# Four-limb point arithmetic for Eisenstein U14 multiplication

Mode 126 keeps the certified scalar representative and fourteen unit-orbit
windows from mode 125, but sums their selected affine points with four-limb
Montgomery Jacobian arithmetic. Each table point is converted during
preparation, one window at a time. A selected nontrivial cube-root unit
costs one four-limb constant product; the point sum uses the same
eleven-product mixed-add polynomial as the Eisenstein-pair path. Its final
affine conversion operates directly on the four-limb accumulator and avoids
the parent's six pair-to-limb conversion products. The [field and group-law
derivation](PROOF.md) shows how the two representations correspond.

## Exact table and preparation resources

| Resource | Mode 125: Eisenstein pair | Mode 126: four limbs | Difference |
| --- | ---: | ---: | ---: |
| Nonidentity U14 affine slots | 1,004,890 | 1,004,890 | 0 |
| Retained table bytes | 78,470,208 | 70,430,960 | 8,039,248 fewer (10.245%) |
| One-process peak RSS, macOS bytes | 346,734,592 | 277,200,896 | 69,533,696 fewer (20.054%) |

The retained-byte values come from each mode's table accounting in the
same release binary. The peak-RSS values are from one verified fixture case
per mode, each launched as a fresh process with macOS `/usr/bin/time -l`.
They include table construction and the online operation. The
[resource outputs](reference-resource.stderr.txt) and
[verification receipt](verification.json) retain both commands, exits,
outputs, and hashes. This one-case RSS comparison describes these exact
processes and allocator conditions. Its CPU times are exploratory because
the host has no isolation receipt.

The first candidate built the complete pair table before conversion. Its
raw [initial record](pre-refactor/README.md) passed correctness but reached
387,989,504 bytes of peak RSS. Converting each window as it is built
removed that extra live table while preserving the final slot count and
point outputs.

## Correctness record

The native release suite passed **79/79** tests. Every converted
nonidentity table point satisfied the secp256k1 curve equation; exact
coordinates and all six unit images matched the pair backend on 512
deterministic slots. Identity, equal/inverse, and 512 nontrivial mixed-add
cases matched the existing group law. Complete mode-125 and mode-126
outputs, representatives, addition counts, and orbit/unit selections
matched on **29,196** boundary, prior-panel, and disjoint new scalar
inputs. The first 128 new points also passed independent binary scalar
replay. Both modes verified all **129** frozen fixture points.

The 4,096-input holdout was generated after protocol commit `1a53e0322`
with seed `20261010726`; its scalar SHA-256 is
`beaffed4a371c99b096d39d0485579fa50592ff1528dd201ce9033079e17c96c`.
The exact field check verifies the cube-root relation and norm/kernel
identities for the reduction map. The final release binary SHA-256 is
`29e12929d4d47e8a32e92bf3ea1aed2b5bccd19a552d7d66c2b89826287b950e`.
The x86-64 Linux release cross-compilation check passed with Rustup's
installed target; physical x86 execution is the next correctness gate.

## Paired online comparison

The [manifest generator](make_isolated_manifest.py) pairs modes 125 and
126 on nine frozen fixture indices for five repetitions. The online
interval includes scalar reduction, Voronoi selection, recoding, table
lookup, unit actions, point arithmetic, final inversion, affine formatting,
and expected-point verification. Shared input decoding and independent
table preparation are outside both online intervals and recorded
separately.
The local manifest structure check emitted nine cases and five repetitions
with SHA-256
`84af5be4d8258c9ed57b65d7dcf4fa201312307ea64b9dcf488f98c9cf530ec8`;
its CPU and NUMA identifiers were placeholders.

The existing RunPod serial queue can replay correctness on physical x86.
Its Docker/cgroup-v1 host fails the repository's strict CPU-isolation gate,
so a controlled wall-time ratio awaits a qualifying host. The memory and
correctness results above do not depend on that CPU timing result.
