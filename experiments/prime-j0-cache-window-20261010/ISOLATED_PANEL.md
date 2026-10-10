# U14/U15/U16 paired online panel

The two candidate comparisons use one host-built executable and the same
129-case secp256k1 fixture. They pair U14 mode 130 separately with U15
mode 131 and U16 mode 132 on case indices `0,16,32,48,64,80,96,112,128`.
The retained point tables are prepared before the online interval. The
interval includes scalar reduction, certified representative selection,
recoding, orbit lookup, grouped additions, final inversion, formatting,
and expected-point verification. Five repetitions are the default.

On an audited Linux host, run the release suite, build the executable,
then run `verify_candidate.py --binary /absolute/path/to/eisenstein_fixed`
from an experiment source tree that contains the frozen input panel. The
verifier writes `verification.json`, hashes the source and raw outputs,
checks all fixture points and the fresh panel, and records peak RSS for
each mode. Move the complete source and verification receipt together to
the isolated host; the receipt is host-specific and must be regenerated
after a rebuild.

Generate the paired manifests from that host's receipt:

```sh
python3 experiments/prime-j0-cache-window-20261010/make_isolated_manifests.py \
  --receipt /absolute/path/to/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output-prefix /absolute/path/to/cache-window-panel
python3 scripts/isolated_bench.py probe /absolute/path/to/cache-window-panel-u15.json
python3 scripts/isolated_bench.py probe /absolute/path/to/cache-window-panel-u16.json
```

Use the actual isolated partition and NUMA node from the host audit in
place of the example values. Submit both manifests to one persistent
`isolated_bench.py serve` process after both preflights pass. The service
serializes them and retains raw paired rows and noise-gate failures.
The RunPod `exp-run` job supplies a Linux correctness replay and a
read-only host probe; its container does not itself certify exclusive
physical CPUs or NUMA memory. The current Pod exposes `tmpfs` instead of
cgroup v2 at `/sys/fs/cgroup`, so its strict isolated-partition preflight
cannot pass. Use an administrator-controlled host or a provider allocation
with equivalent auditable host-level isolation for the paired timing panel.
