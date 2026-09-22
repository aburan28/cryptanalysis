#!/usr/bin/env python3
"""Publish immutable fused-selector benchmark receipts and sources to S3."""
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        while True:
            block = source.read(8 << 20)
            if not block:
                return value.hexdigest()
            value.update(block)


def command(args, check=True):
    result = subprocess.run(args, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result


def publicUrl(bucket, region, key):
    return 'https://%s.s3.%s.amazonaws.com/%s' % (bucket, region, quote(key))


def upload(bucket, region, path, key, sha):
    head = command(['aws', 's3api', 'head-object', '--bucket', bucket,
                    '--key', key, '--output', 'json'], check=False)
    if head.returncode == 0:
        value = json.loads(head.stdout)
        if value.get('ContentLength') != path.stat().st_size or value.get('Metadata', {}).get('sha256') != sha:
            raise ValueError('existing object identity mismatch: ' + key)
    elif not any(token in head.stderr for token in ('404', 'Not Found', 'NoSuchKey')):
        raise RuntimeError(head.stderr.strip())
    else:
        contentType = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        command(['aws', 's3', 'cp', str(path), 's3://%s/%s' % (bucket, key),
                 '--only-show-errors', '--content-type', contentType,
                 '--cache-control', 'public,max-age=31536000,immutable',
                 '--metadata', 'sha256=' + sha])
    url = publicUrl(bucket, region, key)
    anonymous = None
    for attempt in range(6):
        anonymous = command(['aws', 's3api', 'head-object', '--no-sign-request',
                             '--bucket', bucket, '--key', key, '--output', 'json'],
                            check=False)
        if anonymous.returncode == 0:
            break
        if attempt == 5:
            raise RuntimeError(anonymous.stderr.strip())
        time.sleep(1)
    public = json.loads(anonymous.stdout)
    if (public.get('ContentLength') != path.stat().st_size or
            public.get('Metadata', {}).get('sha256') != sha):
        raise ValueError('public object readback mismatch: ' + key)
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--region', default='us-west-2')
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, action='append', required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--manifest-out', type=Path, required=True)
    parser.add_argument('--prefix', default='public/ecc2k130/synthetic-fused-selector/v1')
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text())
    identity = summary.get('benchmarkIdentity', '')
    if not re.fullmatch(r'[0-9a-f]{64}', identity) or summary.get('collectionEnabled') is not False:
        raise ValueError('invalid or collection-enabled summary')
    prefix = args.prefix.strip('/') + '/' + identity
    sourceNames = [
        'metal/fused_benchmark.mm', 'metal/fused_benchmark_extra.metal',
        'metal/fused_reference.py', 'metal/prepare_fused_benchmark.py',
        'metal/run_fused_benchmark.py', 'metal/summarize_fused_benchmarks.py',
        'metal/publish_fused_benchmark.py', 'metal/artifact_walk.metal',
        'metal/artifact_reference.py', 'scripts/mslgen.py']
    files = [('receipts/summary.json', args.summary)]
    files += [('receipts/' + path.name, path) for path in args.receipt]
    files += [('source/' + name.replace('/', '__'), ROOT / name) for name in sourceNames]
    files.append(('bin/metal-fused-benchmark', args.binary))
    records = []
    for relative, path in files:
        sha = digest(path)
        key = prefix + '/' + relative
        records.append({'name': relative, 'bytes': path.stat().st_size,
                        'sha256': sha, 'key': key,
                        'url': upload(args.bucket, args.region, path, key, sha)})
    manifest = {
        'schema': 'ecc2k130-fused-selector-publication-v1',
        'scope': summary['scope'], 'benchmarkIdentity': identity,
        'decision': summary['decision'], 'collectionEnabled': False,
        'namespace': prefix + '/', 'files': records}
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    manifestSha = digest(args.manifest_out)
    manifestKey = prefix + '/manifest.json'
    manifest['manifestUrl'] = upload(args.bucket, args.region, args.manifest_out,
                                     manifestKey, manifestSha)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
