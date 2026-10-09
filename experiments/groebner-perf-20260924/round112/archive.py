"""Losslessly bind source-frozen early-parity evidence in one deduplicated tar."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
DIRECTORIES = (
    'early-parity-initial-v1',
    'early-parity-reference-builds-v1',
    'early-parity-discovery-v1',
    'early-parity-validation-v1',
    'early-parity-validation-v2',
    'early-parity-validation-v3',
    'early-parity-validation-v4',
    'early-parity-profile-v3',
)
FILES = (
    'early-parity-discovery-v1-audit-interrupted.json',
    'early-parity-discovery-v1-audit-source.py',
    'early-parity-discovery-v1-audit.log',
    'early-parity-discovery-v1.log',
    'early-parity-integration-v1.json',
    'early-parity-monitor-v1-interrupted.json',
    'early-parity-monitor-v1.log',
    'early-parity-profile-driver-v1-interrupted.json',
    'early-parity-profile-driver-v2-launch.json',
    'early-parity-profile-driver-v2.log',
    'early-parity-profile-driver-v3-launch.json',
    'early-parity-profile-driver-v3.json',
    'early-parity-profile-driver-v3.log',
    'early-parity-profile-v3.log',
    'early-parity-validation-v3-launch.json',
    'early-parity-validation-v3.log',
    'early-parity-validation-v4-launch.json',
    'early-parity-validation-v4.log',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    tar.addfile(info, io.BytesIO(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    validation = json.loads((evidence/'early-parity-validation-v4/validation.json').read_text())
    profile = json.loads((evidence/'early-parity-profile-v3/report.json').read_text())
    audit = json.loads((evidence/'early-parity-validation-v4/audit.json').read_text())
    controls = json.loads((evidence/'early-parity-validation-v4/artifact-controls.json').read_text())
    assert validation['status'] == profile['status'] == audit['status'] == controls['status'] == 'PASS'
    assert validation['source_commit'] == profile['source_commit']
    assert audit['rows'] == 52 and controls['count'] == 13
    sources = {}
    for label in DIRECTORIES:
        base = evidence/label
        assert base.is_dir() and not base.is_symlink()
        for path in sorted(base.rglob('*')):
            if path.is_file():
                assert not path.is_symlink()
                sources[str(Path(label)/path.relative_to(base))] = path
    for label in FILES:
        path = evidence/label
        assert path.is_file() and not path.is_symlink(), label
        sources[label] = path
    sources['archive.py'] = HERE/'archive.py'
    logical, objects = {}, {}
    for name, path in sorted(sources.items()):
        data = path.read_bytes()
        digest = sha(data)
        logical[name] = dict(sha256=digest, bytes=len(data))
        objects.setdefault(digest, path)
    manifest = dict(schema='early-parity-evidence/1',
        source_commit=validation['source_commit'], source_tree=validation['source_tree'],
        validation='early-parity-validation-v4/validation.json',
        profile='early-parity-profile-v3/report.json',
        logical=logical)
    target = HERE/'results.tar.gz'
    with target.open('wb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as packed:
        with tarfile.open(fileobj=packed, mode='w') as tar:
            add(tar, 'manifest.json', json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()+b'\n')
            for digest, path in sorted(objects.items()):
                add(tar, 'objects/'+digest, path.read_bytes())
    # Verify the gzip stream once in archive order. Random-access extraction
    # seeks backward through gzip for each repeated logical file and is
    # needlessly quadratic on proof-heavy panels.
    decoded, read_manifest, members = {}, None, 0
    with tarfile.open(target, 'r|gz') as tar:
        for member in tar:
            members += 1
            data = tar.extractfile(member).read()
            if member.name == 'manifest.json':
                read_manifest = json.loads(data)
            else:
                assert member.name.startswith('objects/')
                digest = member.name.removeprefix('objects/')
                assert sha(data) == digest
                decoded[digest] = data
    assert read_manifest == manifest and members == len(objects)+1
    for name, entry in logical.items():
        data = decoded[entry['sha256']]
        assert len(data) == entry['bytes'] and data == sources[name].read_bytes(), name
    outer = dict(status='PASS', archive=target.name, sha256=sha(target.read_bytes()),
        bytes=target.stat().st_size, logical_files=len(logical), members=len(objects)+1,
        source_commit=validation['source_commit'], source_tree=validation['source_tree'],
        lossless_byte_verification=True, native_binaries_executed=False)
    (HERE/'archive.json').write_text(json.dumps(outer, indent=2)+'\n')
    print('EARLY_PARITY_ARCHIVE_PASS', len(logical), len(objects), target.stat().st_size)


if __name__ == '__main__':
    main()
