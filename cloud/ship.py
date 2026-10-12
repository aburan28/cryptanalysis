"""Put this checkout on a pod without sending all of it.

The pod fetches the newest commit of the checkout that GitHub already has
(HEAD's merge base with its upstream) from the public repository, and only
the differences cross from here: the changed and untracked files in a small
tarball, with the paths to delete.  A checkout without an upstream or not on
GitHub, or a pod that cannot fetch, gets the whole checkout instead.  The pod
checks the tree it built against this checkout's file names and sizes before
it is used; cloud/install_tree.py then puts it where builds run.

    tree in dest = what `git ls-files --cached --others --exclude-standard`
                   lists here, with this checkout's contents (cloud/tree.py)
"""
import hashlib
import io
import os
import re
import shlex
import subprocess
import tarfile
from pathlib import Path

import tree

# `fetch_base URL COMMIT` puts COMMIT in the pod's cache repository once.  A
# pod starts it at boot for SHIP_PREFETCH (runpod_pod.py's STAGE0), and the
# lock makes a ship that arrives meanwhile wait for that fetch, not repeat it.
# The ref is what the next fetch offers as already here: without one GitHub
# sends the whole tree again (241 s against 1 s on a pod).
FETCH = r"""
cache=${SHIP_CACHE:-/root/.cache/checkout.git}
fetch_base() {
  mkdir -p "$(dirname "$cache")"
  (
    flock 9
    [ -d "$cache" ] || git init -q --bare "$cache"
    git -C "$cache" cat-file -e "$2^{commit}" 2>/dev/null ||
      git -C "$cache" fetch -q --depth=1 "$1" "+$2:refs/ship/base"
  ) 9>"$cache.lock"
}
""".strip()

# Run on the pod as `bash -c SCRIPT ship DEST BASE URL DIGEST`, the overlay on
# stdin.  Exit 3 means the tree it built is not the checkout.
SCRIPT = "set -euo pipefail\ndest=$1 base=$2 url=$3 want=$4\n" + FETCH + "\n" + r"""
tmp=$dest.part
rm -rf "$tmp"
mkdir -p "$tmp"
if [ -n "$base" ]; then
  fetch_base "$url" "$base"
  git -C "$cache" archive "$base" | tar -x -C "$tmp"
fi
tar --no-same-owner -xzf - -C "$tmp"
got=$(python3 - "$tmp" <<'EOF'
import hashlib, os, sys
root = sys.argv[1]
def control(name):
    path = os.path.join(root, name)
    data = open(path, "rb").read().decode("utf-8", "surrogateescape").split("\0")
    os.remove(path)
    return data
for name in control(".ship-deleted"):
    if name and os.path.lexists(os.path.join(root, name)):
        os.remove(os.path.join(root, name))
names = []
for top, dirs, files in os.walk(root):
    names += [os.path.relpath(os.path.join(top, n), root) for n in files]
    names += [os.path.relpath(os.path.join(top, n), root) for n in dirs
              if os.path.islink(os.path.join(top, n))]
digest = hashlib.sha256()
for name in sorted(names):
    digest.update(f"{name}\0{os.lstat(os.path.join(root, name)).st_size}\n".encode())
print(digest.hexdigest())
EOF
)
if [ "$got" != "$want" ]; then
  echo "ship: the tree built in $tmp is not the checkout" >&2
  exit 3
fi
rm -rf "$dest"
mv "$tmp" "$dest"
""".strip()


def git(root, *args):
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    return out.stdout.decode("utf-8", "surrogateescape") if out.returncode == 0 else None


def public_url(root):
    """origin as https://github.com/OWNER/REPO.git, without credentials; None off GitHub."""
    url = (git(root, "remote", "get-url", "origin") or "").strip()
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", url)
    return f"https://github.com/{match[1]}/{match[2]}.git" if match else None


def base_commit(root):
    """The newest commit of HEAD that its upstream has too, or None."""
    upstream = (git(root, "rev-parse", "--verify", "-q", "@{upstream}") or "").strip()
    if not upstream:
        return None
    return (git(root, "merge-base", "HEAD", upstream) or "").strip() or None


def prefetch_env(root):
    """SHIP_PREFETCH for a new pod, "URL COMMIT": the base a ship of this checkout
    builds on, fetched at boot so the first ship need not wait for all of it."""
    base, url = base_commit(root), public_url(root)
    return {"SHIP_PREFETCH": f"{url} {base}"} if base and url else {}


def manifest_digest(root, names):
    """sha256 over the sorted (path, size) pairs; SCRIPT computes the same on the pod."""
    digest = hashlib.sha256()
    for name in sorted(names):
        digest.update(f"{name}\0{os.lstat(Path(root) / name).st_size}\n".encode())
    return digest.hexdigest()


def plan(root, files=None, full=False, url=None):
    """What to send: {base, url, files, overlay, deleted}.  `files` defaults to
    the whole checkout; `full` sends every file and fetches nothing; `url` is
    where the base is fetched from (default: origin, on GitHub)."""
    root = Path(root)
    files = sorted(tree.checkout_files(root) if files is None else files)
    base, url = (None, None) if full else (base_commit(root), url or public_url(root))
    if not (base and url):
        return {"base": None, "url": None, "files": files, "overlay": files, "deleted": []}
    keep = set(files)
    fields = (git(root, "diff", "--name-status", "--no-renames", "-z", base) or "").split("\0")
    changed = {path for status, path in zip(fields[::2], fields[1::2]) if status != "D"}
    in_base = set((git(root, "ls-tree", "-r", "-z", "--name-only", base) or "").split("\0"))
    untracked = set((git(root, "ls-files", "-z", "--others", "--exclude-standard") or "")
                    .split("\0"))
    overlay = sorted((changed | untracked | (keep - in_base)) & keep)
    deleted = sorted((in_base - keep) - {""})
    return {"base": base, "url": url, "files": files, "overlay": overlay, "deleted": deleted}


def overlay_bytes(root, shipment):
    """The overlay tar.gz: the files to write, and .ship-deleted listing the paths
    to drop.  Files over tree.MAX_FILE_BYTES stay behind, as tree.pack leaves
    them, and are dropped on the pod and from the files the digest counts."""
    root = Path(root)
    skipped = [n for n in shipment["overlay"]
               if (root / n).is_file() and not (root / n).is_symlink()
               and (root / n).stat().st_size > tree.MAX_FILE_BYTES]
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for name in shipment["overlay"]:
            if name not in skipped:
                tar.add(root / name, arcname=name, recursive=False)
        listing = "\0".join(shipment["deleted"] + skipped).encode("utf-8", "surrogateescape")
        info = tarfile.TarInfo(".ship-deleted")
        info.size = len(listing)
        tar.addfile(info, io.BytesIO(listing))
    return buf.getvalue(), skipped


def ship(command_prefix, root, dest, files=None, env=None, log=None, url=None):
    """Make `dest` this checkout (or `files` of it) where `command_prefix`
    (an ssh command line, or none for this machine) runs commands, and return a
    summary with the returncode.  Sends everything when the other side cannot
    build the tree from GitHub (or `url`)."""
    root = Path(root)
    for full in (False, True):
        shipment = plan(root, files, full, url)
        data, skipped = overlay_bytes(root, shipment)
        digest = manifest_digest(root, [n for n in shipment["files"] if n not in skipped])
        args = [SCRIPT, "ship", dest, shipment["base"] or "", shipment["url"] or "", digest]
        command = ([*command_prefix, "bash -c " + " ".join(map(shlex.quote, args))]
                   if command_prefix else ["bash", "-c", *args])
        if log:
            log(f"shipping {len(shipment['overlay'])} of {len(shipment['files'])} files, "
                f"{len(data) / 1e6:.1f} MB" + (f", over {shipment['base'][:12]} from GitHub"
                                               if shipment["base"] else ""))
        out = subprocess.run(command, input=data, env=env, check=False)
        summary = {"base": shipment["base"], "files": len(shipment["files"]) - len(skipped),
                   "sent_files": len(shipment["overlay"]) - len(skipped),
                   "deleted": len(shipment["deleted"]), "bytes": len(data), "skipped": skipped,
                   "returncode": out.returncode}
        if out.returncode == 0 or shipment["base"] is None:
            return summary
        if log:
            log(f"could not build the tree over {shipment['base'][:12]}; sending all of it")
    return summary
