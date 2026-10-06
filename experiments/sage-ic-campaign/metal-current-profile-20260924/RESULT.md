# Current Sage CPU and Apple Metal point-map cost

Eight fresh installed Sage workers measured degree-131 Frobenius point maps
after the native codec and table changes. Each cell has twelve balanced
native/CPU/Metal orders, exact point checks, and cleanup in the complete-call
median. Hardware was an Apple M4 Pro; source and binary identities are frozen
in `intent.json` and each raw receipt.

| Points | Power | Run | Native Sage ms | CPU table ms | Metal ms | Metal / CPU speed |
| ---: | ---: | :---: | ---: | ---: | ---: | ---: |
| 1,024 | 65 | A | 12.460 | 1.576 | 3.240 | 0.486× |
| 1,024 | 65 | B | 12.690 | 1.612 | 3.264 | 0.494× |
| 4,096 | 65 | A | 34.718 | 4.207 | 8.293 | 0.507× |
| 4,096 | 65 | B | 34.216 | 2.456 | 7.270 | 0.338× |
| 16,384 | 65 | A | 162.053 | 12.138 | 21.387 | 0.568× |
| 16,384 | 65 | B | 155.229 | 15.253 | 24.536 | 0.622× |
| 4,096 | 1 | A | 7.674 | 2.618 | 8.831 | 0.296× |
| 4,096 | 1 | B | 5.708 | 2.533 | 6.956 | 0.364× |

The CPU table beats Metal in every frozen complete-call cell. Metal beats
native Sage for power 65 in all six cells; the power-1 cells favor both CPU
and native Sage over Metal. This is a measured dispatch boundary on this
installation, not a universal hardware rule. Cold setup plus first verified
call was roughly 10–34 ms for CPU and 46–99 ms for Metal; charge that setup
to the declared workload before making a full IC claim.

The separate stage profile split complete CPU/Metal calls into packing,
packed mapping, point reconstruction, verification, and cleanup. Each stage
case used one fresh worker and seed, with twelve alternating rounds.

| Points | Power | CPU map ms | Metal map ms | Metal device ms | CPU unpack ms | Metal unpack ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,024 | 65 | 0.179 | 1.902 | 0.029 | 0.595 | 0.631 |
| 4,096 | 65 | 0.396 | 1.893 | 0.036 | 2.687 | 2.774 |
| 16,384 | 65 | 0.379 | 2.147 | 0.094 | 4.477 | 11.686 |
| 4,096 | 1 | 0.380 | 1.140 | 0.035 | 2.854 | 2.549 |

At 1,024 and 4,096 points, the packed Metal map call accounts for most of
the measured Metal/CPU gap while device execution is a small part of that
call. At 16,384 points, reconstruction after Metal was also slower in this
profile; its twelve-round sequence repeats that observation, but a second
profile is needed before assigning a cause. The next Metal experiment should
time host copies, command creation, and output-buffer access inside
`bh_metal_apply`, then test one change against complete point calls and peak
RSS. A kernel-only gain would have little effect on the measured gap.

These are Sage point-map measurements. The local degree-131 IC runner uses
its own ONB arithmetic and SAT/F5 path; no verified recovered-log IC
speedup, calibrated operation ratio, or rho-boundary claim follows.
