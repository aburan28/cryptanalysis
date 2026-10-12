"""Lossless bounded Git parts for an otherwise unchanged compressed archive."""
import hashlib
import json
from pathlib import Path

SCHEMA = 'factor-base-compressed-parts/1'
SUFFIX = '.chunks.json'
MAX_PART = 80 * 1024 * 1024
MAX_PAYLOAD = 1024 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= set('0123456789abcdef')


def metadata(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 1024 * 1024:
        raise ValueError('invalid chunk manifest file')
    record = json.loads(path.read_text())
    if set(record) != {'schema', 'codec', 'bytes', 'sha256', 'parts'} or record['schema'] != SCHEMA:
        raise ValueError('invalid chunk manifest schema')
    if record['codec'] not in ('gz', 'xz') or not path.name.endswith('.'+record['codec']+SUFFIX):
        raise ValueError('invalid chunk codec or filename')
    if type(record['bytes']) is not int or not 0 < record['bytes'] <= MAX_PAYLOAD or not valid_hash(record['sha256']):
        raise ValueError('invalid chunk payload identity')
    parts = record['parts']
    if not isinstance(parts, list) or not 1 <= len(parts) <= 4096:
        raise ValueError('invalid chunk count')
    stem = path.name[:-len(SUFFIX)]
    for i, part in enumerate(parts):
        if not isinstance(part, dict) or set(part) != {'name', 'bytes', 'sha256'}:
            raise ValueError('invalid chunk record')
        if part['name'] != f'{stem}.part-{i:04d}':
            raise ValueError('invalid chunk path or order')
        if type(part['bytes']) is not int or not 0 < part['bytes'] <= MAX_PART or not valid_hash(part['sha256']):
            raise ValueError('invalid chunk size or digest')
    if sum(p['bytes'] for p in parts) != record['bytes']:
        raise ValueError('chunk lengths do not sum to the payload length')
    return record


def paths(path):
    path = Path(path)
    record = metadata(path)
    return [path, *[path.parent/p['name'] for p in record['parts']]]


def read(path):
    path = Path(path)
    record = metadata(path)
    buffers = []
    for part in record['parts']:
        item = path.parent/part['name']
        if item.is_symlink() or item.stat().st_size != part['bytes']:
            raise ValueError('chunk file type or size mismatch')
        blob = item.read_bytes()
        if digest(blob) != part['sha256']:
            raise ValueError('chunk digest mismatch')
        buffers.append(blob)
    blob = b''.join(buffers)
    if len(blob) != record['bytes'] or digest(blob) != record['sha256']:
        raise ValueError('reassembled payload identity mismatch')
    return blob


def write(path, blob, codec, part_bytes):
    path = Path(path)
    if type(part_bytes) is not int or not 1 <= part_bytes <= MAX_PART:
        raise ValueError('invalid chunk byte limit')
    if codec not in ('gz', 'xz') or not path.name.endswith('.'+codec+SUFFIX):
        raise ValueError('invalid chunk codec or filename')
    if not 0 < len(blob) <= MAX_PAYLOAD or (len(blob)+part_bytes-1)//part_bytes > 4096:
        raise ValueError('chunk payload exceeds supported limits')
    record = dict(schema=SCHEMA, codec=codec, bytes=len(blob), sha256=digest(blob), parts=[])
    stem = path.name[:-len(SUFFIX)]
    path.parent.mkdir(parents=True, exist_ok=True)

    def put(destination, content):
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or destination.read_bytes() != content:
                raise ValueError('refusing to replace different archive content')
            return
        # Exclusive creation preserves a conflicting writer's existing bytes.
        with destination.open('xb') as stream:
            stream.write(content)

    for i, offset in enumerate(range(0, len(blob), part_bytes)):
        content = blob[offset:offset+part_bytes]
        name = f'{stem}.part-{i:04d}'
        put(path.parent/name, content)
        record['parts'].append(dict(name=name, bytes=len(content), sha256=digest(content)))
    # Publish the manifest only after all of its immutable parts exist.
    put(path, (json.dumps(record, sort_keys=True, indent=2)+'\n').encode())
    assert metadata(path) == record
    return record
