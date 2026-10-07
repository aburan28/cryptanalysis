base: 91c13f5866100da4db082ca889dbe10f23bf3b8a (aburan28/cairn main)
branch: cursor/agent-unconfined-gpus-f26c
title: feat(agent): let a host that is the jail run GPU jobs unconfined, and probe only the GPUs a container can open

## What this changes, and why

A rented GPU box is often a container itself: a Runpod or Vast pod, with no
container engine and no `/dev/kvm` inside. Running `cairn agent` there as an
executor hit two problems.

**1. A GPU job could not run at all.** Neither jail can be built in such a pod
and no engine can pass a device, so the pod is the jail and its operator runs
jobs with `--sandbox none`. `choose` then refused every job with `gpus > 0`:
"a GPU job needs an engine to pass the device, so it cannot run unconfined".
That refusal protects the receipt, not the card. An unconfined job runs as the
agent's user and can already open whatever devices that user can, so a job
that declared `gpus: 0` used the GPU anyway, and its receipt said it asked for
none.

`--unconfined-gpus` (`CAIRN_AGENT_UNCONFINED_GPUS=1`, on `run`, `exec` and
`install`) is that operator saying so explicitly:

- A job that asks for `none` and for GPUs runs.
- Its receipt lists `gpus` under `unenforced`, beside `isolation`, with a note
  naming the flag.
- The registration's `jobs` block carries `"unconfined_gpus": true`.
- The flag is refused (exit 2) on a host whose operator chose any jail, where
  it could do nothing. A jail still needs an engine to pass a GPU; only `none`
  changes.

**2. The probe counted the host's GPUs, not the pod's.** Inside a container
`/sys/bus/pci` is the host's bus. On a pod given one RTX 5090 on an eight-card
host, the probe listed all eight cards and the host's BMC display, and a node
summing registrations counted capacity nobody there could use.

`nvidia-smi` lists only the GPUs this process can open. Once it has answered,
an NVIDIA GPU it does not list is now left out, and `No devices were found`
leaves out every one. A host where `nvidia-smi` is missing or fails otherwise
reports the bus as before.

Measured on a Runpod pod (one RTX 5090 on an eight-card Xeon Gold 6530 host),
running this branch's binary beside the 1.17.0 release:

| | cairn 1.17.0 | this branch |
|---|---|---|
| `agent probe` GPUs | 9: eight RTX 5090s and the BMC display | 2: the pod's RTX 5090 (with its memory) and the BMC display |
| GPU job, `--sandbox none` | refused, exit 3 | refused, exit 3, naming `--unconfined-gpus` |
| the same with `--unconfined-gpus` | — | ran `nvidia-smi -L`, which listed the RTX 5090; receipt `succeeded`, `gpus_requested: 1`, `unenforced: [isolation…, gpus…]` |
| `--unconfined-gpus` without `--sandbox none` | — | usage error, exit 2 |
| the node's roster (`GET /hosts`) | — | `jobs.unconfined_gpus: true`, 2 GPUs |

Not changed:

- **The BMC display is still listed.** A server's management VGA (ASPEED,
  `pci:1a03`) is still reported as a GPU, on bare metal as in a pod. It is a
  separate question what counts as an accelerator.
- **Memory is still read from `/proc/meminfo`.** In a container that is the
  host's memory. The `cgroup` block shows the cap where the cgroup is v2; a
  cgroup v1 cap is still not read.

## Consensus surface

Did this touch a record, a hash, or an encoding?

- [x] No. Registrations are not records; the `jobs` block travels through
      the node opaque.

## Checks

- [x] `cargo test --locked --all-targets`: 2,074 passed, none failed.
- [x] `cargo test --locked --all-targets --all-features`: 2,074 passed, none
      failed.
- [ ] `cargo test --manifest-path reference/rust/Cargo.toml`: not run;
      `reference/` is untouched.
- [x] `cargo fmt --check`; `cargo clippy --all-targets -- -D warnings`, with
      and without `--all-features`.
- [x] `RUSTDOCFLAGS="-D warnings" cargo doc --no-deps --locked --all-features`
- [ ] `./scripts/interop.sh`: not applicable; no record changed.
- [x] `./scripts/agent-demo.sh`, which now checks:
  - a GPU job under `none` is refused without the flag, with a receipt that
    names it;
  - with the flag it runs, and `gpus` is listed as unenforced;
  - the flag is a usage error on a host that jails its jobs;
  - `install --print` writes `CAIRN_AGENT_UNCONFINED_GPUS` only when the flag
    is given;
  - the registration says `unconfined_gpus: false` by default.

New unit tests:
- `sandbox`: only `none` changes, and only with the operator's flag.
- `job`: an unconfined GPU job is refused, then runs with `gpus` unenforced.
- `cli`: the flag needs `--sandbox none`.
- `probe`: the measured pod's bus and `nvidia-smi` rows.

## Threat model

- [x] Not applicable.

The flag gives a job nothing it could not already open: an unconfined job runs
as the agent's user, with whatever devices that user can reach. The flag only
changes whether such a job may *say* it wants a GPU and have its receipt say
how it got one. Isolation is `none` either way, and the floor rule still keeps
a job from asking for `none` on a host whose operator did not choose it.
