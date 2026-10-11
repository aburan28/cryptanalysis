#!/usr/bin/env python3
"""Select, download and read public synthetic ECC2K-130 pair tables.

This manages precomputed data. It does not change the production walk or
provide an intermediate-branch predictor. No AWS credentials are used to read
the public catalog or payloads.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

SCHEMA = 'ecc2k-public-pair-catalog-v1'
DEFAULT_CATALOG = Path(__file__).resolve().parent / 'tables' / 'catalog.json'
MAX_CATALOG = 1 << 20


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        while data := source.read(8 << 20):
            h.update(data)
    return h.hexdigest()


def validate_catalog(catalog):
    if catalog.get('schema') != SCHEMA or catalog.get('scope') != 'synthetic-precomputation-only':
        raise ValueError('unsupported table catalog')
    domain = catalog.get('domain', {})
    if (domain.get('fieldDegree') != 131 or domain.get('knownScalar') != 65537 or
            domain.get('polynomial') != 'z^131+z^13+z^2+z+1'):
        raise ValueError('unsupported table domain')
    seen = set()
    artifacts = catalog.get('artifacts', [])
    if not artifacts:
        raise ValueError('catalog has no artifacts')
    for entry in artifacts:
        identity = entry.get('id', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', identity) or identity in seen:
            raise ValueError('unsafe or repeated artifact ID')
        seen.add(identity)
        h = entry.get('branches')
        if type(h) is not int or h not in (128, 256):
            raise ValueError('unsupported branch count')
        directions = 262 * h
        count = directions * (directions + 1) // 2
        if (entry.get('signedDirections') != directions or entry.get('entries') != count or
                entry.get('entryBytes') != 36 or entry.get('runtimeStatus') != 'pair-sums-only'):
            raise ValueError('invalid pair-table geometry/status')
        files = entry.get('files', [])
        if {f.get('name') for f in files} != {'pairs.bin', 'directions.bin', 'coefficients.json', 'table.json'} or len(files) != 4:
            raise ValueError('incomplete artifact file set')
        for item in files:
            if (type(item.get('bytes')) is not int or item['bytes'] <= 0 or
                    not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', ''))):
                raise ValueError('invalid file size/checksum')
            key = item.get('key', '')
            parts = key.split('/')
            if (not re.fullmatch(r'[A-Za-z0-9/_.-]+', key) or key.startswith('/') or
                    any(p in ('', '.', '..') for p in parts)):
                raise ValueError('unsafe object key')
        files = {f['name']: f for f in files}
        if files['pairs.bin']['bytes'] != count * 36 or files['directions.bin']['bytes'] != directions * 36:
            raise ValueError('payload size does not match geometry')
        if files['coefficients.json']['bytes'] > MAX_CATALOG or files['table.json']['bytes'] > MAX_CATALOG:
            raise ValueError('oversized metadata')
    return catalog


def public_url(url):
    parts = urlsplit(url)
    if parts.username or parts.password or parts.fragment:
        raise ValueError('URL must not contain credentials/fragments')
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('public table URLs require HTTPS')
    return url


def load_catalog(location=None):
    location = str(location or os.environ.get('CRYPTANALYSIS_TABLE_CATALOG') or DEFAULT_CATALOG)
    if urlsplit(location).scheme in ('https', 'http'):
        public_url(location)
        with urlopen(location, timeout=30) as response:
            public_url(response.url)
            data = response.read(MAX_CATALOG + 1)
        base = location
    else:
        with Path(location).open('rb') as source:
            data = source.read(MAX_CATALOG + 1)
        base = None
    if len(data) > MAX_CATALOG:
        raise ValueError('catalog too large')
    catalog = validate_catalog(json.loads(data))
    if catalog.get('publicBaseUrl'):
        base = public_url(catalog['publicBaseUrl'].rstrip('/') + '/')
    return catalog, base


def cuda_memory(device=None):
    """Query one physical NVIDIA GPU; never sum memory across GPUs."""
    if device is None:
        visible = os.environ.get('CUDA_VISIBLE_DEVICES')
        if visible is not None:
            if not visible.strip() or visible.strip() == '-1':
                raise ValueError('CUDA_VISIBLE_DEVICES exposes no GPU')
            device = visible.split(',')[0].strip()
        else:
            device = '0'
    result = subprocess.run(['nvidia-smi', '-i', str(device),
                             '--query-gpu=uuid,memory.total,memory.free',
                             '--format=csv,noheader,nounits'], text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError('cannot query GPU memory; supply --free-vram-gb for explicit planning')
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1:
        raise ValueError('GPU selection must resolve to exactly one device')
    uuid, total, free = [v.strip() for v in lines[0].split(',')]
    total, free = int(total) * (1 << 20), int(free) * (1 << 20)
    if not 0 <= free <= total:
        raise ValueError('invalid GPU memory report')
    return {'backend': 'cuda', 'device': str(device), 'uuid': uuid, 'totalBytes': total, 'freeBytes': free}


def metal_memory(device=None):
    """Query Metal's working-set recommendation, not a global free-VRAM value."""
    helper = Path(__file__).resolve().parent / 'build' / 'metal-pair-table'
    if not helper.is_file():
        raise ValueError('build the native Metal helper first: make -C %s' % (Path(__file__).resolve().parent / 'metal'))
    command = [str(helper), 'info']
    if device is not None:
        command.append(str(device))
    result = subprocess.run(command, text=True, capture_output=True, timeout=30)
    try:
        info = json.loads(result.stdout)
    except ValueError:
        raise ValueError('Metal helper did not return a device report') from None
    if result.returncode or info.get('status') != 'ok':
        raise ValueError(info.get('error', 'Metal GPU is unavailable'))
    selected, host = info['device'], info['host']
    budget = selected['recommendedWorkingSetBytes']
    maximum = selected['maxBufferBytes']
    if type(budget) is not int or budget <= 0 or type(maximum) is not int or maximum < 36:
        raise ValueError('invalid Metal device memory report')
    return {'backend': 'metal', **selected, 'host': host,
            'planningBudgetBytes': budget,
            'budgetMeaning': 'Metal recommended working set, not global free GPU memory; allocation still needs checking'}


def gpu_memory(device=None, backend='auto'):
    if backend == 'auto':
        backend = 'metal' if sys.platform == 'darwin' else 'cuda'
    if backend == 'cuda':
        return cuda_memory(device)
    if backend == 'metal':
        return metal_memory(device)
    raise ValueError('unsupported GPU backend')


def select_for_hardware(catalog, hardware, reserve_bytes=2 << 30):
    if hardware.get('backend') != 'metal':
        return select(catalog, hardware['freeBytes'], reserve_bytes)
    plan = select(catalog, hardware['planningBudgetBytes'], reserve_bytes)
    if plan is not None:
        plan['planningBudgetBytes'] = plan.pop('freeGpuBytes')
        plan['remainingPlanningBytes'] = plan.pop('remainingGpuBytes')
        maximum = hardware['maxBufferBytes'] // 36 * 36
        payload = next(f['bytes'] for f in plan['artifact']['files'] if f['name'] == 'pairs.bin')
        plan['metalBuffersRequired'] = (payload + maximum - 1) // maximum
        plan['requiresSegmentedMetalLoader'] = plan['metalBuffersRequired'] > 1
        plan['selectionMeaning'] = 'Metal working-set plan only; not a successful allocation or performance measurement'
    return plan


def select(catalog, free_bytes, reserve_bytes=2 << 30):
    if type(free_bytes) is not int or type(reserve_bytes) is not int or min(free_bytes, reserve_bytes) < 0:
        raise ValueError('invalid memory budget')
    eligible = []
    for entry in catalog['artifacts']:
        required = sum(f['bytes'] for f in entry['files'] if f['name'].endswith('.bin')) + reserve_bytes
        if required <= free_bytes:
            eligible.append((entry['branches'], entry, required))
    if not eligible:
        return None
    _, entry, required = max(eligible, key=lambda item: item[0])
    return {'artifact': entry, 'domain': catalog['domain'], 'freeGpuBytes': free_bytes, 'reserveBytes': reserve_bytes,
            'requiredGpuBytes': required, 'remainingGpuBytes': free_bytes - required,
            'selectionMeaning': 'largest fitting pair-sum artifact; not a measured performance ranking'}


def download_file(item, url, destination):
    """Stream/resume a single immutable object, verify before atomic rename."""
    public_url(url)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.partial')
    with destination.with_name(destination.name + '.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if destination.exists():
            if destination.stat().st_size != item['bytes'] or digest(destination) != item['sha256']:
                raise ValueError('cached file failed verification: ' + str(destination))
            return str(destination)
        offset = partial.stat().st_size if partial.exists() else 0
        if offset > item['bytes']:
            raise ValueError('partial download exceeds expected size')
        if shutil.disk_usage(destination.parent).free < item['bytes'] - offset + (8 << 20):
            raise ValueError('insufficient disk space for table download')
        h = hashlib.sha256()
        if offset:
            with partial.open('rb') as old:
                while data := old.read(8 << 20):
                    h.update(data)
        if offset < item['bytes']:
            headers = {'Accept-Encoding': 'identity'}
            if offset:
                headers['Range'] = 'bytes=%d-' % offset
            request = Request(url, headers=headers)
            with urlopen(request, timeout=60) as response:
                public_url(response.url)
                if offset:
                    expected = 'bytes %d-%d/%d' % (offset, item['bytes'] - 1, item['bytes'])
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise ValueError('server did not honor the resume range')
                elif response.status != 200:
                    raise ValueError('unexpected download status')
                length = response.headers.get('Content-Length')
                if length is not None and int(length) != item['bytes'] - offset:
                    raise ValueError('HTTP payload size differs from catalog')
                with partial.open('ab') as output:
                    while data := response.read(8 << 20):
                        if offset + len(data) > item['bytes']:
                            raise ValueError('download exceeds catalog size')
                        output.write(data); h.update(data); offset += len(data)
                    output.flush(); os.fsync(output.fileno())
        if offset != item['bytes'] or h.hexdigest() != item['sha256']:
            raise ValueError('incomplete download or SHA-256 mismatch; partial retained for diagnosis')
        partial.rename(destination)
        return str(destination)


def fetch(selection, base, cache):
    if not base:
        raise ValueError('catalog is not published: supply its HTTPS URL or publicBaseUrl')
    entry = selection['artifact']
    payload = next(f for f in entry['files'] if f['name'] == 'pairs.bin')
    directory = Path(cache) / entry['id'] / payload['sha256']
    paths = {}
    # Small metadata first; a failed access check need not start an 81 GB transfer.
    for item in sorted(entry['files'], key=lambda f: f['bytes']):
        paths[item['name']] = download_file(item, urljoin(base, item['key']), directory / item['name'])
    receipt = {'schema': 'ecc2k-table-cache-v1', 'id': entry['id'], 'branches': entry['branches'],
               'signedDirections': entry['signedDirections'], 'entries': entry['entries'],
               'domain': selection['domain'],
               'payloadSha256': payload['sha256'], 'files': paths,
               'runtimeStatus': entry['runtimeStatus']}
    with tempfile.NamedTemporaryFile(mode='w', dir=directory, prefix='ready-', suffix='.tmp', delete=False) as out:
        json.dump(receipt, out, indent=2); out.write('\n')
        out.flush(); os.fsync(out.fileno())
        ready = Path(out.name)
    ready.replace(directory / 'ready.json')
    return receipt


class PairTable:
    """Read pair sums using constant host memory and 64-bit file offsets.

    Construct from the verified cache receipt returned by fetch(). The caller
    supplies direction indices for this artifact's branch count.
    """
    def __init__(self, receipt, expected_domain=None):
        if receipt.get('schema') != 'ecc2k-table-cache-v1':
            raise ValueError('expected a verified cache receipt')
        self.domain = receipt.get('domain')
        if expected_domain is not None and self.domain != expected_domain:
            raise ValueError('table curve/generator/target does not match the consumer')
        self.branches = receipt['branches']
        self.directions = receipt['signedDirections']
        if (self.branches not in (128, 256) or self.directions != 262 * self.branches or
                receipt['entries'] != self.directions * (self.directions + 1) // 2):
            raise ValueError('invalid cache receipt geometry')
        self.file = Path(receipt['files']['pairs.bin']).open('rb')
        if os.fstat(self.file.fileno()).st_size != receipt['entries'] * 36:
            self.file.close(); raise ValueError('cached table size changed')
        self.coefficients = None
        if 'coefficients.json' in receipt['files']:
            try:
                self.coefficients = json.loads(Path(receipt['files']['coefficients.json']).read_text())
                if self.coefficients['branches'] != self.branches:
                    raise ValueError('coefficient branch count mismatch')
                if self.domain is not None:
                    for key in ('ell', 'frobeniusEigenvalue', 'generatorPolynomial', 'targetPolynomial', 'knownScalar'):
                        if self.coefficients[key] != self.domain[key]:
                            raise ValueError('coefficient domain mismatch')
            except Exception:
                self.file.close(); raise

    def direction(self, h, k, eps=0):
        if not 0 <= h < self.branches or not 0 <= k < 131 or eps not in (0, 1):
            raise ValueError('invalid direction')
        return 2 * (k * self.branches + h) + eps

    def lookup(self, u, v):
        if not 0 <= u < self.directions or not 0 <= v < self.directions:
            raise ValueError('direction index outside the selected table')
        u, v = sorted((u, v))
        raw = os.pread(self.file.fileno(), 36, 36 * (v * (v + 1) // 2 + u))
        if len(raw) != 36:
            raise ValueError('short table read')
        w = struct.unpack('<9I', raw)
        if w == (0,) * 8 + (0x80000000,):
            return None
        if w[8] & ~63:
            raise ValueError('invalid point encoding')
        return (sum(w[i] << (32 * i) for i in range(4)) | ((w[8] & 7) << 128),
                sum(w[i + 4] << (32 * i) for i in range(4)) | ((w[8] >> 3) << 128))

    def close(self):
        self.file.close()

    def pair_coefficients(self, u, v):
        if self.coefficients is None:
            raise ValueError('coefficient metadata is required')
        if not 0 <= u < self.directions or not 0 <= v < self.directions:
            raise ValueError('direction index outside the selected table')
        ell = int(self.coefficients['ell'])
        eigen = int(self.coefficients['frobeniusEigenvalue'])
        a, b = 0, 0
        for direction in (u, v):
            k, h = divmod(direction // 2, self.branches)
            row = self.coefficients['rows'][h]
            factor = pow(eigen, k, ell) * (-1 if direction & 1 else 1)
            a = (a + factor * int(row['a'])) % ell
            b = (b + factor * int(row['b'])) % ell
        return a, b

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('select', 'fetch'))
    parser.add_argument('--catalog')
    parser.add_argument('--backend', choices=('auto', 'cuda', 'metal'), default='auto', help='auto uses Metal on macOS and CUDA elsewhere')
    parser.add_argument('--device', help='NVIDIA index/UUID or Metal index/registry ID')
    parser.add_argument('--free-vram-gb', type=float, help='explicit planning budget in decimal GB; otherwise query the GPU')
    parser.add_argument('--reserve-gib', type=float, default=2, help='memory reserved for runtime, buffers and other allocations')
    parser.add_argument('--cache', type=Path, default=Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'cryptanalysis' / 'tables')
    args = parser.parse_args(argv)
    try:
        catalog, base = load_catalog(args.catalog)
        hardware = gpu_memory(args.device, args.backend) if args.free_vram_gb is None else {'freeBytes': int(args.free_vram_gb * 1e9), 'source': 'explicit override'}
        selection = select_for_hardware(catalog, hardware, int(args.reserve_gib * (1 << 30)))
        if selection is None:
            print(json.dumps({'status': 'no-fitting-table', 'hardware': hardware})); return 1
        if args.command == 'fetch':
            result = fetch(selection, base, args.cache)
        else:
            result = selection
        print(json.dumps({'status': 'ok', 'hardware': hardware, **result}, indent=2))
        return 0
    except (OSError, ValueError, OverflowError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)})); return 2


if __name__ == '__main__':
    sys.exit(main())
