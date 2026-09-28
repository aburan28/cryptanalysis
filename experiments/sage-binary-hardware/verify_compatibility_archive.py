"""Verify the published compatibility evidence without Sage or device access."""
import hashlib
import json
from pathlib import Path
import tarfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    here = Path(__file__).resolve().parent
    evidence = here/'compatibility-20260928'
    manifest = json.loads((evidence/'MANIFEST.json').read_text())
    for name, expected in manifest['files'].items():
        require(digest((evidence/name).read_bytes()) == expected, name)
    local = json.loads((evidence/'local-MANIFEST.json').read_text())
    for name, expected in manifest['omitted_binaries'].items():
        require(local['files'][name] == expected, name)
        require(not (evidence/name).exists(), 'compiled binary should not be distributed: '+name)
    for run in ('installed-001', 'installed-002', 'unavailable-backends'):
        report = json.loads((evidence/run/'receipt.json').read_text())
        for item in [report['validator'], *report['tests']]:
            path = evidence/run/'sources'/Path(item['path']).name
            require(digest(path.read_bytes()) == item['sha256'], str(path))
    installed = json.loads((evidence/'installed-002/receipt.json').read_text())
    require(installed['status'] == 'pass', 'installed validation did not pass')
    groups = [installed['scalar_and_batch'], *installed['backends'].values()]
    require(sum(group['tests'] for group in groups) == 18, 'expected 18 test groups')
    require(all(group['status'] == 'pass' and not any(group[key] for key in
                ('failures', 'errors', 'skipped')) for group in groups), 'failed or skipped group')
    checksums = []
    for arch in ('arm64', 'x86_64'):
        record = json.loads((evidence/f'native-{arch}/receipt.json').read_text())
        require(record['status'] == 'pass' and record['ubsan'], arch)
        require(record['result']['cases'] == 30, 'expected 30 native cases')
        require(record['result']['architecture'] == arch, 'native architecture mismatch')
        require(record['execution'] == ('native' if arch == 'arm64' else 'rosetta'), arch)
        for path, expected in record['source_sha256'].items():
            require(digest((evidence/'sources'/Path(path).name).read_bytes()) == expected, path)
        checksums.append(record['result']['checksum'])
    require(checksums[0] == checksums[1], 'architecture checksums differ')
    missing = json.loads((evidence/'unavailable-backends/receipt.json').read_text())
    require(missing['status'] == 'fail' and all(result['status'] == 'fail'
            for result in missing['backends'].values()), 'unavailable backends must not pass')

    for folder in ('five-opportunities-20260925', 'pari-result-20260926'):
        target = here.parent/'sage-ic-campaign'/folder
        index = json.loads((target/'measurement-manifest.json').read_text())
        archive = target/'measurement-evidence.tar.gz'
        require(digest(archive.read_bytes()) == index['archive_sha256'], str(archive))
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            require(len(members) == len(index['files']), 'archive member count differs')
            require({entry.name for entry in members} == set(index['files']), 'archive paths differ')
            for entry in members:
                require(entry.isfile(), 'expected a regular evidence file')
                require(not Path(entry.name).is_absolute() and '..' not in Path(entry.name).parts,
                        'invalid evidence path')
                require(digest(tar.extractfile(entry).read()) == index['files'][entry.name], entry.name)
            require(tar.extractfile('selected.patch').read() == (target/'selected.patch').read_bytes(),
                    'published patch differs from measured archive')
            if folder.startswith('five-'):
                decision = json.load(tar.extractfile('FINAL_DECISION.json'))['decisions']
                require(all(decision[key]['status'] == 'PASS_LOCAL' for key in ('pari', 'batch', 'fused')),
                        'selected candidate did not pass')
                require(all(decision[key]['status'] == 'HOLD' for key in ('singleton', 'table')),
                        'held candidates changed status')
            else:
                decision = json.load(tar.extractfile('run-002/summary.json'))
                require(decision['status'] == 'PASS_LOCAL', 'PARI result candidate did not pass')
    print('Verified compatibility evidence, 18 installed groups, 60 native cases, and both arithmetic archives.')


if __name__ == '__main__':
    main()
