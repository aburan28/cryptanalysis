"""Restore the original JSON bytes from the compressed, hash-pinned receipts."""
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    index = json.loads((HERE/'evidence-index.json').read_text())
    for name, metadata in index['files'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or path.suffix != '.json':
            raise ValueError('unsafe evidence path')
        compressed = HERE/(name+'.gz')
        if hashlib.sha256(compressed.read_bytes()).hexdigest() != metadata['gzip_sha256']:
            raise ValueError(f'compressed evidence hash mismatch: {name}')
        with gzip.open(compressed, 'rb') as stream:
            data = stream.read(metadata['bytes']+1)
        if len(data) != metadata['bytes'] or hashlib.sha256(data).hexdigest() != metadata['sha256']:
            raise ValueError(f'evidence content hash mismatch: {name}')
        target = HERE/path
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f'refusing to replace changed local evidence: {name}')
        target.write_bytes(data)
    print(f'Restored {len(index["files"])} original JSON receipts; all hashes match.')


if __name__ == '__main__':
    main()
