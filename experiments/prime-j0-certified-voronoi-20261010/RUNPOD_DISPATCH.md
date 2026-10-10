# RunPod x86 correctness dispatch

The source package contains 18 tracked files from public branch
`codex/prime-j0-certified-voronoi-20261010` at commit `360287659`.
Repository visibility was checked as public before transfer. The archive
SHA-256 is `0659687274d43312fcd5eaadc8d1dfc910278d82088cb768b4ea77b2543ad2fa`;
the same digest passed `sha256sum -c` on the pod before unpacking.

The existing RunPod pod `zbeg026fw61so1` (`isolated_blush_stork`) has an
active N131 CryptoMiniSat job
`20261008T042104Z_n131-formula-replay_ECgd5M`. It predates the runner's
serial lock and its frozen `launch.sh` therefore did not acquire that lock.
The first certified Voronoi submission,
`20261010T005212Z_prime-j0-certified-voronoi_6EK6Px`, started
concurrently. It was interrupted immediately, and `exp-run status` records
`failed`, exit code `130`; this is a dispatch failure, not a correctness result.

A temporary `legacy-serial-bridge` process on the pod now holds
`/workspace/experiment-runs/.serial.lock` while the N131 tmux session is
running. It releases the lock when that session ends. The certified run was
resubmitted as `20261010T005324Z_prime-j0-certified-voronoi_UwTC1K`.
The post-submission check reported **queued** for this run and **running**
for N131, with the bridge ready file naming N131 as lock holder and no
`cargo` or `eisenstein_fixed` process. The new job will run the complete
native release test suite and both 129-point fixture checks, one at a time
after N131 completes.

The remote result directory is
`/workspace/experiment-runs/20261010T005324Z_prime-j0-certified-voronoi_UwTC1K`.
The pod's Docker/cgroup-v1 topology fails the host isolation gate; any
elapsed times in this run are exploratory. Export the result directory after
completion because this pod's container overlay is not durable storage.
