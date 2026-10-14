# Linux replay and isolation preflight, 2026-10-09

The frozen U14, U15, and U16 secp256k1 generator paths passed the Linux
correctness replay: all 129 fixture scalars per format and one direct
single-case dispatch per format. The release binary was built from source
snapshot `60d56390502558c7d09b40bf7a488a5b5ea0b110` on the existing
RunPod CPU Pod `zbeg026fw61so1` (`isolated_blush_stork`) with Rust 1.93.1.
Its SHA-256 is
`2643c2e7314ec473a3e6811683741317d00a3506b2f390ae79cf2eb09c8fe5c3`.
The [checker receipt](unit-orbit-cli-check-linux.json) binds that binary to
the exact source, fixture, protocol, and checker hashes. The
[build log](build.log) and [checker log](check.log) preserve command output.
The check did not use its local timing values.

Two source-verified five-repetition manifests are frozen for the same nine
fixture scalars: [U14 versus U15](u14-vs-u15.json) and
[U14 versus U16](u14-vs-u16.json). They use one Linux binary and differ only
in the method flag. Their manifest hashes are respectively
`3dbb800a3413b7fb8bec851f7ed9cbf56e1bd9b3038b34f7bf5dab3c68710c86`
and
`8df4b2b2cde308978e357d241abcb2e5fbc7e9b6e78810c2f4dd49bf6cd5e357`.
The absolute paths identify the Pod staging snapshot; regenerate manifests
when moving the snapshot to a qualified host.

The long-running serial service was active on the Pod, with one previous
queued job recorded as `rejected`. The strict preflight returned `ok: false`
and 22 problems for [U14/U15](u14-vs-u15-preflight.json) and
[U14/U16](u14-vs-u16-preflight.json). The Pod is a Docker container with a
cgroup v1 host configuration. There is no isolated cgroup or `nohz_full` CPU
set; the service may run on benchmark CPUs, SMT siblings fall outside the
requested set, frequencies are not fixed, and IRQ affinity overlaps it.
Consequently no timed panel was submitted and the controlled online ratio
remains unknown. The service and correctness replay can be used for future
deployment checks; controlled timing requires a host that passes the exact
manifest preflight before queue submission.
