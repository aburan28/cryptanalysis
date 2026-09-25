"""Pack this checkout for a remote job, and merge the job's outputs back.

A job sees exactly what `git ls-files --cached --others --exclude-standard`
lists: tracked files with their uncommitted edits plus untracked files that
are not ignored.  Ignored build trees stay behind unless named with
`include`.
"""
import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 100 * 1024 * 1024


def repo_root(start=None):
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or os.getcwd(),
                         capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def checkout_files(root):
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                         cwd=root, capture_output=True, check=True)
    names = {n for n in out.stdout.decode("utf-8", "surrogateescape").split("\0") if n}
    return sorted(n for n in names if os.path.lexists(root / n))


def git_state(root):
    def git(*args):
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    return {"commit": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain"))}


def _expand(root, paths):
    out = []
    for rel in paths:
        path = (root / rel).resolve()
        if root.resolve() not in (path, *path.parents):
            raise ValueError(f"{rel} is outside the checkout")
        if path.is_dir():
            out += [str(p.relative_to(root.resolve())) for p in path.rglob("*")
                    if p.is_file() or p.is_symlink()]
        elif path.exists():
            out.append(str(path.relative_to(root.resolve())))
        else:
            raise FileNotFoundError(rel)
    return out


def pack(root, include=(), max_file_bytes=MAX_FILE_BYTES):
    """Return (tar.gz bytes, summary) for the checkout at root."""
    root = Path(root)
    names = sorted(set(checkout_files(root)) | set(_expand(root, include)))
    skipped = []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for name in names:
            path = root / name
            if path.is_file() and not path.is_symlink() and path.stat().st_size > max_file_bytes:
                skipped.append(name)
                continue
            tar.add(path, arcname=name, recursive=False)
    data = buf.getvalue()
    return data, {"files": len(names) - len(skipped), "skipped": skipped, "bytes": len(data)}


def _safe(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def merge_outputs(data, dest, tag, seen):
    """Unpack a job's out.tar.gz into dest.

    `seen` maps path -> sha256 across the shards of one job: a path another
    shard already wrote with different content lands beside it as
    `<path>.<tag>` instead of overwriting it.  Returns the paths written,
    relative to dest.
    """
    dest = Path(dest)
    written = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        for member in tar:
            if not member.isfile() or not _safe(member.name):
                continue
            source = tar.extractfile(member)
            digest = hashlib.sha256()
            with tempfile.NamedTemporaryFile(dir=dest, delete=False) as tmp:
                for chunk in iter(lambda: source.read(1 << 20), b""):
                    digest.update(chunk)
                    tmp.write(chunk)
            name = member.name
            if seen.get(name, digest.hexdigest()) != digest.hexdigest():
                name = f"{name}.{tag}"
            else:
                seen[name] = digest.hexdigest()
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(tmp.name, target)
            os.chmod(target, (member.mode & 0o777) or 0o644)
            written.append(name)
    return written
