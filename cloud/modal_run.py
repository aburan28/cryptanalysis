#!/usr/bin/env python3
"""Run a command from this checkout on Modal CPU or GPU containers.

  run [options] -- CMD...     start the job; stream it (or --detach) and copy results back
  status JOB                  each shard's state, exit code, runtime and hardware
  logs JOB [--shard I] [-f]   a shard's log
  fetch JOB [--dest DIR]      copy a finished job's results back
  list [-n N]                 recent jobs
  kill JOB                    terminate a job's containers
  gc [--days N]               delete job records older than N days

`run` packs the checkout (tracked files with their edits, plus untracked files
that are not ignored), uploads it once to the Modal volume
cryptanalysis-remote-jobs, and starts one sandbox per shard in the Modal app
cryptanalysis-remote.  Each shard runs CMD in a fresh copy of the checkout
with SHARD_INDEX and SHARD_COUNT set, then returns the paths named by --out
(and, with --changed, every file CMD wrote) into this checkout.  When two
shards write the same path with different contents, the later one lands as
PATH.shard<I>.  The exit status is the first failing shard's, else 0.

Images (built on first use, then cached by Modal):
  cpu   Ubuntu 24.04: gcc, cmake, Rust stable, Go, valgrind, iverilog,
        verilator, yosys, msolve 0.10.1 ($MSOLVE), pycryptosat, python-sat
  cuda  the same on nvidia/cuda:12.8.1-devel, plus the CUDA 13.3 compiler
        that ecc2k130 needs at $CUDA13_HOME/bin/nvcc
  sage  SageMath 10.9 from conda-forge (`sage`, `sage -python`)

GPUs: T4, L4, A10G, L40S, A100-40GB, A100-80GB, H100, H200, B200,
RTX-PRO-6000; "H100:2" asks for two.  Credentials: MODAL_TOKEN_ID and
MODAL_TOKEN_SECRET, or a profile from `modal token set`.
"""
import argparse
import calendar
import io
import json
import os
import shlex
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tree  # noqa: E402

APP_NAME = "cryptanalysis-remote"
VOLUME_NAME = "cryptanalysis-remote-jobs"
MOUNT = "/jobs"
WORKDIR = "/work/repo"
MAX_TIMEOUT = 24 * 3600

APT = ["build-essential", "cmake", "ninja-build", "pkg-config", "autoconf", "automake",
       "libtool", "m4", "git", "curl", "ca-certificates", "jq", "unzip", "zstd", "xz-utils",
       "time", "bc", "file", "procps", "libgmp-dev", "libmpfr-dev", "libflint-dev",
       "libssl-dev", "libffi-dev", "zlib1g-dev", "golang-go", "valgrind", "iverilog",
       "verilator", "yosys"]
PIP = ["pycryptosat==5.15.0", "python-sat==1.9.dev15", "numpy", "sympy", "pytest"]
SYSTEM_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULTS = {"cpu": {"cpu": 8.0, "memory": 16.0, "gpu": None},
            "cuda": {"cpu": 8.0, "memory": 32.0, "gpu": "L4"},
            "sage": {"cpu": 8.0, "memory": 32.0, "gpu": None}}


def modal():
    try:
        import modal as module
    except ImportError:
        sys.exit("the Modal client is missing: pip install modal")
    return module


def image_for(kind, apt=(), pip=()):
    m = modal()
    if kind == "sage":
        image = (m.Image.micromamba(python_version="3.12")
                 .apt_install("build-essential", "git", "curl", "ca-certificates", "time", "procps")
                 .micromamba_install("sage=10.9", channels=["conda-forge"]))
    else:
        cuda = kind == "cuda"
        base = "nvidia/cuda:12.8.1-devel-ubuntu24.04" if cuda else "ubuntu:24.04"
        path = "/opt/cargo/bin:/opt/msolve/bin:" + (
            "/usr/local/nvidia/bin:/usr/local/cuda/bin:" if cuda else "") + SYSTEM_PATH
        image = (m.Image.from_registry(base, add_python="3.12")
                 .entrypoint([])
                 .env({"DEBIAN_FRONTEND": "noninteractive", "TZ": "Etc/UTC"})
                 .apt_install(*APT)
                 .env({"CARGO_HOME": "/opt/cargo", "RUSTUP_HOME": "/opt/rustup", "PATH": path})
                 .run_commands(
                     "curl -fsSL https://sh.rustup.rs | sh -s -- -y -q --profile minimal "
                     "--default-toolchain stable -c clippy -c rustfmt --no-modify-path",
                     "git clone -q --depth 1 --branch v0.10.1 "
                     "https://github.com/algebraic-solving/msolve /tmp/msolve && cd /tmp/msolve "
                     "&& ./autogen.sh >/dev/null && ./configure -q --prefix=/opt/msolve "
                     "&& make -s -j8 && make -s install && rm -rf /tmp/msolve")
                 .pip_install(*PIP)
                 .env({"MSOLVE": "/opt/msolve/bin/msolve"}))
        if cuda:
            image = (image.add_local_file(HERE.parent / "ecc2k130" / "scripts" / "fetch_cuda.sh",
                                          "/opt/fetch_cuda.sh", copy=True)
                     .run_commands("sh /opt/fetch_cuda.sh /opt/cuda-13.3")
                     .env({"CUDA13_HOME": "/opt/cuda-13.3"}))
    if apt:
        image = image.apt_install(*apt)
    if pip:
        image = image.pip_install(*pip)
    return image.env({"PYTHONUNBUFFERED": "1"})


def volume():
    return modal().Volume.from_name(VOLUME_NAME, create_if_missing=True, version=2)


def read_bytes(vol, path, attempts=1):
    for attempt in range(attempts):
        try:
            return b"".join(vol.read_file(path))
        except Exception:  # Modal raises NotFoundError for a missing path
            if attempt + 1 < attempts:
                time.sleep(3)
    return None


def read_json(vol, path, attempts=1):
    data = read_bytes(vol, path, attempts)
    return json.loads(data) if data else None


def put(vol, files):
    with vol.batch_upload(force=True) as batch:
        for path, data in files.items():
            batch.put_file(io.BytesIO(data), path)


def job_meta(vol, job):
    meta = read_json(vol, f"{job}/job.json")
    if meta is None:
        sys.exit(f"no job {job} in the volume {VOLUME_NAME}")
    return meta


def new_job_id():
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + os.urandom(2).hex()


def shard_env(job, shard, shards, command, outs, changed, extra, memory_gib=None):
    env = {**extra,
           "JOB_ID": job, "JOB_DIR": f"{MOUNT}/{job}/shards/{shard}", "JOB_WORKDIR": WORKDIR,
           "JOB_SRC": f"{MOUNT}/{job}/src.tar.gz", "JOB_CMD": command,
           "JOB_OUTS": "\n".join(outs), "JOB_CHANGED": "1" if changed else "0",
           "SHARD_INDEX": str(shard), "SHARD_COUNT": str(shards)}
    if memory_gib:
        env["JOB_MEM_GB"] = f"{memory_gib:g}"
    return env


def parse_env(pairs):
    env = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            sys.exit(f"--env wants KEY=VALUE, not {pair!r}")
        env[key] = value
    return env


def stream(sandbox, prefix, lock):
    pending = ""
    for chunk in sandbox.stdout:
        pending += chunk
        *lines, pending = pending.split("\n")
        with lock:
            for line in lines:
                sys.stdout.write(f"{prefix}{line}\n")
            sys.stdout.flush()
    if pending:
        with lock:
            print(f"{prefix}{pending}", flush=True)


def collect(vol, job, shards, dest):
    """Merge every shard's outputs into dest; return {shard: status or None}."""
    seen, statuses = {}, {}
    for shard in range(shards):
        base = f"{job}/shards/{shard}"
        statuses[shard] = read_json(vol, f"{base}/status.json", attempts=5)
        data = read_bytes(vol, f"{base}/out.tar.gz", attempts=2 if statuses[shard] else 1)
        if data:
            for path in tree.merge_outputs(data, dest, f"shard{shard}", seen):
                print(f"  fetched {path}", file=sys.stderr)
    return statuses


def exit_code(statuses, returncodes):
    for shard, status in sorted(statuses.items()):
        rc = status["returncode"] if status else (returncodes.get(shard) or 1)
        if rc:
            return rc
    return 0


def cmd_run(args):
    m = modal()
    command = shlex.join(args.command) if len(args.command) > 1 else args.command[0]
    defaults = DEFAULTS[args.image]
    cpu = args.cpu or defaults["cpu"]
    memory = args.memory or defaults["memory"]
    gpu = None if args.gpu == "none" else (args.gpu or defaults["gpu"])
    timeout = min(args.timeout, MAX_TIMEOUT)
    root = tree.repo_root()
    data, summary = tree.pack(root, include=args.include)
    job = new_job_id()
    meta = {"job": job, "created": time.time(), "command": command, "image": args.image,
            "cpu": cpu, "memory_gib": memory, "gpu": gpu, "timeout": timeout,
            "shards": args.shards, "outs": args.out, "changed": args.changed,
            "git": tree.git_state(root), "pack": {k: summary[k] for k in ("files", "bytes")},
            "sandboxes": []}
    hardware = f"{cpu:g} CPU, {memory:g} GiB" + (f", GPU {gpu}" if gpu else "")
    print(f"job {job}: {args.shards} x {args.image} ({hardware}); uploading {summary['files']} "
          f"files, {summary['bytes'] / 1e6:.1f} MB", file=sys.stderr)
    for skipped in summary["skipped"]:
        print(f"  skipped large file {skipped} (pass --include to ship it)", file=sys.stderr)

    vol = volume()
    put(vol, {f"/{job}/src.tar.gz": data, f"/{job}/job.json": json.dumps(meta).encode()})
    app = m.App.lookup(APP_NAME, create_if_missing=True)
    image = image_for(args.image, args.apt, args.pip)
    secrets = [m.Secret.from_name(name) for name in args.secret]
    extra = parse_env(args.env)
    runner = (HERE / "job_runner.sh").read_text()
    sandboxes = []
    with m.enable_output():
        for shard in range(args.shards):
            sandboxes.append(m.Sandbox.create(
                "bash", "-c", runner, app=app, image=image, cpu=cpu, memory=int(memory * 1024),
                gpu=gpu, timeout=timeout, volumes={MOUNT: vol}, secrets=secrets, workdir="/",
                env=shard_env(job, shard, args.shards, command, args.out, args.changed, extra,
                              memory),
                tags={"job": job, "shard": str(shard)}))
    meta["sandboxes"] = [sb.object_id for sb in sandboxes]
    put(vol, {f"/{job}/job.json": json.dumps(meta).encode()})

    if args.detach:
        for sb in sandboxes:
            sb.detach()
        me = "cloud/modal_run.py"
        print(f"started {job}\n  {me} status {job}\n  {me} logs {job} -f\n"
              f"  {me} fetch {job}   (once it finishes)\n  {me} kill {job}")
        return 0

    lock = threading.Lock()
    threads = [threading.Thread(target=stream, daemon=True,
                                args=(sb, f"[{i}] " if args.shards > 1 else "", lock))
               for i, sb in enumerate(sandboxes)]
    for t in threads:
        t.start()
    returncodes = {}
    try:
        for i, sb in enumerate(sandboxes):
            sb.wait(raise_on_termination=False)
            returncodes[i] = sb.returncode
    except KeyboardInterrupt:
        print(f"\ninterrupted; the job keeps running (`cloud/modal_run.py kill {job}` stops it)",
              file=sys.stderr)
        return 130
    for t in threads:
        t.join(timeout=10)
    statuses = collect(vol, job, args.shards, root)
    for shard, status in sorted(statuses.items()):
        if status is None:
            print(f"shard {shard}: ended with {returncodes.get(shard)} and no status "
                  f"(timeout after {timeout} s, or out of memory?)", file=sys.stderr)
    return exit_code(statuses, returncodes)


def cmd_status(args):
    m, vol = modal(), volume()
    meta = job_meta(vol, args.job)
    print(f"job {args.job}: {meta['command']}\n  {meta['shards']} x {meta['image']} "
          f"({meta['cpu']:g} CPU, {meta['memory_gib']:g} GiB, GPU {meta['gpu'] or 'none'}); "
          f"commit {(meta['git'].get('commit') or '?')[:12]}{' +edits' if meta['git'].get('dirty') else ''}")
    for shard in range(meta["shards"]):
        status = read_json(vol, f"{args.job}/shards/{shard}/status.json")
        if status:
            gpus = ", ".join(status.get("gpus") or []) or "no GPU"
            state = (f"exit {status['returncode']} after {status['seconds']:.0f} s on "
                     f"{status['cpus']} CPUs ({gpus}), {status['outputs']} output files")
        else:
            rc = None
            ids = meta.get("sandboxes") or []
            if shard < len(ids):
                rc = m.Sandbox.from_id(ids[shard]).poll()
            state = "running" if rc is None else f"ended with {rc} and no status"
        print(f"  shard {shard}: {state}")
    return 0


def cmd_logs(args):
    vol = volume()
    meta = job_meta(vol, args.job)
    shards = range(meta["shards"]) if args.shard == "all" else [int(args.shard)]
    offsets = dict.fromkeys(shards, 0)
    while True:
        for shard in shards:
            data = read_bytes(vol, f"{args.job}/shards/{shard}/log.txt") or b""
            text = data[offsets[shard]:].decode(errors="replace")
            offsets[shard] = len(data)
            prefix = f"[{shard}] " if len(shards) > 1 else ""
            for line in text.splitlines():
                print(prefix + line)
        done = all(read_bytes(vol, f"{args.job}/shards/{s}/status.json") for s in shards)
        if not args.follow or done:
            return 0
        sys.stdout.flush()
        time.sleep(5)


def cmd_fetch(args):
    vol = volume()
    meta = job_meta(vol, args.job)
    dest = Path(args.dest) if args.dest else tree.repo_root()
    dest.mkdir(parents=True, exist_ok=True)
    statuses = collect(vol, args.job, meta["shards"], dest)
    missing = [s for s, status in statuses.items() if status is None]
    if missing:
        print(f"shards still running or failed without a status: {missing}", file=sys.stderr)
    return 0


def cmd_list(args):
    vol = volume()
    names = sorted((e.path.strip("/") for e in vol.listdir("/")), reverse=True)[:args.n]
    for name in names:
        meta = read_json(vol, f"{name}/job.json") or {}
        done = sum(1 for e in (vol.listdir(f"{name}/shards", recursive=True)
                               if meta.get("shards") else [])
                   if e.path.endswith("status.json"))
        print(f"{name}  {done}/{meta.get('shards', '?')} done  {meta.get('image', '?'):4}  "
              f"{(meta.get('command') or '')[:80]}")
    return 0


def cmd_kill(args):
    m, vol = modal(), volume()
    for sandbox_id in job_meta(vol, args.job).get("sandboxes", []):
        m.Sandbox.from_id(sandbox_id).terminate()
        print(f"terminated {sandbox_id}")
    return 0


def cmd_gc(args):
    vol = volume()
    cutoff = time.time() - args.days * 86400
    for entry in vol.listdir("/"):
        name = entry.path.strip("/")
        try:
            created = calendar.timegm(time.strptime(name[:15], "%Y%m%d-%H%M%S"))
        except ValueError:
            continue
        if created < cutoff:
            vol.remove_file(f"/{name}", recursive=True)
            print(f"removed {name}")
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="run a command on Modal")
    s.add_argument("--image", choices=sorted(DEFAULTS), default="cpu")
    s.add_argument("--cpu", type=float, help="cores (default 8)")
    s.add_argument("--memory", type=float, help="GiB (default 16 for cpu, 32 for cuda/sage)")
    s.add_argument("--gpu", help="GPU type, e.g. L4, H100, RTX-PRO-6000, H100:2 (cuda default L4)")
    s.add_argument("--timeout", type=int, default=3600, help="seconds per shard (max 86400)")
    s.add_argument("--shards", type=int, default=1, help="parallel copies; see SHARD_INDEX")
    s.add_argument("--out", action="append", default=[], metavar="PATH",
                   help="path (relative to the repo root) to copy back; repeatable")
    s.add_argument("--changed", action="store_true",
                   help="copy back every file the command created or modified")
    s.add_argument("--include", action="append", default=[], metavar="PATH",
                   help="also ship this ignored path; repeatable")
    s.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    s.add_argument("--secret", action="append", default=[], metavar="NAME",
                   help="attach a Modal secret by name; repeatable")
    s.add_argument("--apt", action="append", default=[], metavar="PKG", help="extra apt package")
    s.add_argument("--pip", action="append", default=[], metavar="PKG", help="extra pip package")
    s.add_argument("--detach", action="store_true", help="return once the shards start")
    s.set_defaults(fn=cmd_run, command=[])

    for name, fn, help_text in (("status", cmd_status, "shard states"),
                                ("kill", cmd_kill, "terminate a job")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("job")
        s.set_defaults(fn=fn)

    s = sub.add_parser("logs", help="a shard's log")
    s.add_argument("job")
    s.add_argument("--shard", default="0", help="shard index or 'all'")
    s.add_argument("-f", "--follow", action="store_true")
    s.set_defaults(fn=cmd_logs)

    s = sub.add_parser("fetch", help="copy a job's results back")
    s.add_argument("job")
    s.add_argument("--dest", help="directory to unpack into (default: the repo root)")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("list", help="recent jobs")
    s.add_argument("-n", type=int, default=15)
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("gc", help="delete old job records")
    s.add_argument("--days", type=float, default=14)
    s.set_defaults(fn=cmd_gc)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        split = argv.index("--")
        argv, command = argv[:split], argv[split + 1:]
    args = parser().parse_args(argv)
    if args.cmd == "run":
        args.command = command
        if not command:
            sys.exit("run needs a command: cloud/modal_run.py run [options] -- CMD...")
        if args.shards < 1:
            sys.exit("--shards must be at least 1")
    elif command:
        sys.exit(f"{args.cmd} takes no command after --")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
