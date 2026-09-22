"""Permanent, bucket-wide seed identities and exclusive process ownership.

Seed bits are run[16] / lane[32] / restart[16]. A storage prefix is NOT a
seed namespace. This registry deliberately has no automatic lock expiry:
loss of contact does not establish that a GPU stopped. Crash recovery must
confirm the old process is dead before clearing its recorded owner.
"""
import contextlib
import json
import os
import struct
import subprocess
import tempfile
import time
import uuid

PREFIX = "seed-registry/curve-131/"
CONFIG_KEY = PREFIX + "config.json"


class SeedConflict(RuntimeError):
    pass


def checkpoint_iteration(path, run_id):
    """A full checkpoint for this curve/run, never the 40-byte status header.

    The client still validates its complete format and build geometry before
    walking; this gate proves only identity, nonempty state and progress.
    """
    if not os.path.exists(path):
        return None
    with open(path, "rb") as source:
        header = source.read(40)
        state = source.read(1)
    if len(header) != 40 or not state or header[:8] != b"ECC2K130":
        raise SeedConflict("a full resumable checkpoint is required")
    version, curve, threads, batch, lanes, saved_id, iteration = struct.unpack("<6IQ", header[8:])
    if curve != 131 or saved_id != run_id or not all((version, threads, batch, lanes)):
        raise SeedConflict("checkpoint seed identity or geometry is invalid")
    if threads * batch * lanes > 2 ** 32:
        raise SeedConflict("checkpoint lane count exceeds the 32-bit seed namespace")
    return iteration


def run_key(run_id):
    if isinstance(run_id, bool) or not isinstance(run_id, int) or not 1 <= run_id <= 65535:
        raise SeedConflict("run id must be an integer from 1 to 65535")
    return PREFIX + "run-%05d.json" % run_id


def slot_stream(prefix, slot, backend="s3"):
    return "%s-slots:%s:%d" % (backend, prefix.strip("/"), int(slot))


def modal_stream(run_id):
    return "modal-volume:ecc2k130:curve131:run%d" % int(run_id)


class S3Json:
    """Use the same AWS CLI credentials as the workers; no SDK dependency."""
    def __init__(self, bucket):
        if not bucket:
            raise SeedConflict("ECC_BUCKET is required for the shared seed registry")
        self.bucket = bucket

    def read(self, key):
        with tempfile.TemporaryDirectory(prefix="ecc-seed-read-") as tmp:
            path = os.path.join(tmp, "record.json")
            proc = subprocess.run(["aws", "s3api", "get-object", "--bucket", self.bucket,
                                   "--key", key, path, "--output", "json"],
                                  capture_output=True, text=True)
            if proc.returncode:
                if "NoSuchKey" in proc.stderr or "(404)" in proc.stderr:
                    return None, None
                raise SeedConflict("cannot read shared seed registry; launch refused")
            with open(path) as source:
                return json.load(source), json.loads(proc.stdout)["ETag"]

    def cas(self, key, value, etag=None):
        with tempfile.TemporaryDirectory(prefix="ecc-seed-write-") as tmp:
            path = os.path.join(tmp, "record.json")
            with open(path, "w") as output:
                json.dump(value, output, sort_keys=True)
            args = ["aws", "s3api", "put-object", "--bucket", self.bucket, "--key", key,
                    "--body", path, "--content-type", "application/json"]
            args += ["--if-match", etag] if etag else ["--if-none-match", "*"]
            proc = subprocess.run(args, capture_output=True, text=True)
            if proc.returncode == 0:
                return True
            if any(x in proc.stderr for x in ("PreconditionFailed", "(412)", "ConditionalRequestConflict")):
                return False
            raise SeedConflict("cannot update shared seed registry; launch refused")


class SeedRegistry:
    def __init__(self, store, clock=time.time):
        self.store = store
        self.clock = clock

    def ready(self):
        config, _ = self.store.read(CONFIG_KEY)
        if not config or config.get("version") != 1 or config.get("state") != "ready":
            raise SeedConflict("seed registry has not been audited and initialized")

    def next_modal_run(self, used_ids=()):
        """Suggestion only: acquisition still uses compare-and-set at launch."""
        self.ready()
        used = set(used_ids)
        for rid in range(8000, 9000):
            if rid in used or rid + 1000 in used:
                continue
            if all(self.store.read(run_key(n))[0] is None for n in (rid, rid + 1000)):
                return rid
        raise SeedConflict("Modal GPU/CPU seed pairs are exhausted")

    def acquire(self, run_id, stream, checkpoint, owner=None):
        key = run_key(run_id)
        if not stream:
            raise SeedConflict("a permanent stream identity is required")
        self.ready()
        iteration = checkpoint_iteration(checkpoint, run_id)
        owner = owner or uuid.uuid4().hex
        for _ in range(8):
            row, etag = self.store.read(key)
            if row is None:
                row = dict(version=1, run_id=run_id, stream=stream, started=False,
                           checkpoint_floor=0, created_at=self.clock())
            if row.get("version") != 1 or row.get("run_id") != run_id or row.get("stream") != stream:
                raise SeedConflict("run %d is permanently assigned to another stream" % run_id)
            if row.get("blocked"):
                raise SeedConflict("run %d is retired or quarantined" % run_id)
            if row.get("active_owner"):
                raise SeedConflict("run %d already has an owner; confirm it stopped before recovery" % run_id)
            if row.get("started") and iteration is None:
                raise SeedConflict("run %d was already used; refusing to restart its seeds from zero" % run_id)
            if iteration is not None and iteration < int(row.get("checkpoint_floor", 0)):
                raise SeedConflict("run %d checkpoint is older than recorded progress" % run_id)
            row.update(started=True, active_owner=owner, acquired_at=self.clock(),
                       checkpoint_floor=max(int(row.get("checkpoint_floor", 0)), iteration or 0))
            if self.store.cas(key, row, etag):
                return owner
        raise SeedConflict("seed ownership contention; launch refused")

    def release(self, run_id, owner, checkpoint):
        iteration = checkpoint_iteration(checkpoint, run_id)
        key = run_key(run_id)
        for _ in range(8):
            row, etag = self.store.read(key)
            if not row or row.get("active_owner") != owner:
                raise SeedConflict("seed ownership changed; refusing release")
            row.update(active_owner=None, released_at=self.clock(),
                       checkpoint_floor=max(int(row.get("checkpoint_floor", 0)), iteration or 0))
            if self.store.cas(key, row, etag):
                return
        raise SeedConflict("could not release seed ownership; recovery is required")


@contextlib.contextmanager
def worker_guard(worker, slot, run_id):
    """All cloud slot backends share one seed registry at the bucket root."""
    if int(worker.cfg.get("curve", 0)) != 131 or not hasattr(worker.store, "bucket"):
        yield
        return
    name = type(worker.slots).__name__
    if name == "S3Slots":
        backend = "s3"
    elif name == "DynamoSlots":
        backend = "dynamodb:" + worker.slots.table
    elif name == "PostgresSlots":
        backend = "rds:" + worker.slots.campaign
    else:
        raise SeedConflict("unknown production slot authority")
    registry = SeedRegistry(S3Json(worker.store.bucket))
    stream = slot_stream(getattr(worker.store, "prefix", ""), slot, backend)
    token = registry.acquire(run_id, stream, worker.ckptPath)
    try:
        yield
    finally:
        # Never unlock merely because the supervisor raised an exception.
        # A live child still owns its seeds even when it lost its supervisor.
        if worker.proc is None or worker.proc.poll() is not None:
            registry.release(run_id, token, worker.ckptPath)


@contextlib.contextmanager
def modal_guard(run_id, checkpoint, stopped):
    registry = SeedRegistry(S3Json(os.environ.get("ECC_BUCKET")))
    token = registry.acquire(run_id, modal_stream(run_id), checkpoint)
    try:
        yield
    finally:
        if stopped():
            registry.release(run_id, token, checkpoint)
