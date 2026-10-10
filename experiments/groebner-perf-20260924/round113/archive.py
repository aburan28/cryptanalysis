"""Losslessly bind phase, full-query GPU, and separator evidence."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
DIRECTORIES = (
    'continuation-phase-panel-v1',
    'continuation-phase-panel-v2',
    'continuation-phase-panel-v3',
    'continuation-phase-profile-v1',
    'continuation-phase-profile-v2',
    'f4-gpu-query-host-v1',
    'f4-gpu-query-host-v2',
    'f4-gpu-query-host-v3',
    'f4-gpu-query-host-v4',
    'f4-gpu-query-host-v5',
    'f4-gpu-query-host-v6',
    'f4-gpu-query-host-v7',
    'f5-gpu-query-host-v1',
    'f5-gpu-query-host-v2',
    'f5-gpu-query-host-v3',
    'f5-gpu-query-host-v4',
    'f4-gpu-query-scan-v1',
)
FILES = (
    'f6-s3-chain-profile-v2.json',
    'f6-s3-chain-profile-v3.json',
    'isolated-host-preflight-container-v1.json',
    'f4-gpu-emulator-v1.json',
    'f4-gpu-emulator-v1.log',
    'f4-gpu-emulator-v2.json',
    'f4-gpu-emulator-v2.log',
    'f4-f5-cross-engine-host-v1.json',
    'f4-f5-cross-engine-host-v2.json',
    'f4-f5-cross-engine-host-v3.json',
    'f4-f5-cross-engine-host-v4.json',
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
    phase = json.loads((evidence/'continuation-phase-panel-v3/report.json').read_text())
    repeated = json.loads((evidence/'continuation-phase-profile-v2/report.json').read_text())
    scan = json.loads((evidence/'f4-gpu-query-scan-v1/report.json').read_text())
    host = json.loads((evidence/'f4-gpu-query-host-v7/report.json').read_text())
    f5_host = json.loads((evidence/'f5-gpu-query-host-v4/report.json').read_text())
    cross = json.loads((evidence/'f4-f5-cross-engine-host-v4.json').read_text())
    chain = json.loads((evidence/'f6-s3-chain-profile-v3.json').read_text())
    assert (phase['status'] == repeated['status'] == scan['status'] == host['status']
            == f5_host['status'] == cross['status'] == 'PASS')
    assert len(phase['rows']) == 10 and len(repeated['rows']) == 30
    assert len(scan['rows']) == 41 and len(host['rows']) == len(f5_host['rows']) == 9
    assert len(cross['pairs']) == 9 and all(pair['same_verified_answer'] for pair in cross['pairs'])
    assert host['binary_sha256'] == f5_host['binary_sha256'] == cross['binary_sha256']
    committed_benchmark = subprocess.check_output(
        ['git', 'show', cross['source_commit']+':suite/examples/f4_query_bench.rs'],
        cwd=HERE)
    assert committed_benchmark == (HERE.parents[2]/'suite/examples/f4_query_bench.rs').read_bytes()
    assert all(row['execution'] == 'completed' for row in phase['rows']+repeated['rows']
               +scan['rows']+host['rows']+f5_host['rows'])
    assert all(row['status'] == 'PLANTED_CHAIN_EQUATIONS_VERIFIED' for row in chain)
    assert [row['induced_width'] for row in chain] == [15, 21, 21, 21]
    assert all(row['left_to_right_width'] == row['theorem_bound'] for row in chain)
    emulator = json.loads((evidence/'f4-gpu-emulator-v2.json').read_text())
    assert emulator['status'] == 'PASS' and not emulator['gpu_physical']
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
    sources['phase-build-receipt.json'] = HERE/'build/receipt.json'
    logical, objects = {}, {}
    for name, path in sorted(sources.items()):
        data = path.read_bytes()
        digest = sha(data)
        logical[name] = dict(sha256=digest, bytes=len(data))
        objects.setdefault(digest, path)
    manifest = dict(schema='groebner-continuation-evidence/1',
        phase_commit=phase['source_commit'], profile_commit=repeated['source_commit'],
        phase='continuation-phase-panel-v3/report.json',
        profile='continuation-phase-profile-v2/report.json',
        gpu_f4_host='f4-gpu-query-host-v7/report.json',
        gpu_f5_host='f5-gpu-query-host-v4/report.json',
        gpu_cross_engine='f4-f5-cross-engine-host-v4.json',
        gpu_scan='f4-gpu-query-scan-v1/report.json',
        separator='f6-s3-chain-profile-v3.json', logical=logical)
    target = HERE/'results.tar.gz'
    staged = HERE/'results.tar.gz.tmp'
    assert not staged.exists()
    with staged.open('wb') as stream, gzip.GzipFile(filename='', mode='wb', fileobj=stream,
                                                   mtime=0) as packed:
        with tarfile.open(fileobj=packed, mode='w') as tar:
            add(tar, 'manifest.json',
                json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()+b'\n')
            for digest, path in sorted(objects.items()):
                add(tar, 'objects/'+digest, path.read_bytes())
    decoded, read_manifest, members = {}, None, 0
    with tarfile.open(staged, 'r|gz') as tar:
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
    outer = dict(status='PASS', archive=target.name, sha256=sha(staged.read_bytes()),
        bytes=staged.stat().st_size, logical_files=len(logical), members=members,
        phase_commit=phase['source_commit'], profile_commit=repeated['source_commit'],
        lossless_byte_verification=True, qualified_speedup=None)
    staged.replace(target)
    (HERE/'archive.json').write_text(json.dumps(outer, indent=2)+'\n')
    print('CONTINUATION_ARCHIVE_PASS', len(logical), len(objects), target.stat().st_size)


if __name__ == '__main__':
    main()
