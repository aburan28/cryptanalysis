#!/usr/bin/env python3
"""Prepare and publish immutable public pair tables; publish the catalog last.

Credentials come from the normal AWS CLI environment/profile. This script
never changes bucket/account access policies. Public GET must already work
for the chosen prefix. Local source paths are excluded from public metadata.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import table_store

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / 'research' / 'step_table'
VARIANTS = ('pair128-24gb-20260921', 'pair256-88gb-20260921')


def prepare(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    artifacts, uploads, domain = [], [], None
    for variant in VARIANTS:
        source = RESEARCH / variant
        manifest = json.loads((source / 'manifest.json').read_text())
        coeffs = json.loads((source / 'coefficients.json').read_text())
        if not manifest['complete']:
            raise ValueError('table generation is incomplete')
        currentDomain = {'fieldDegree': 131, 'polynomial': manifest['polynomial'],
                         'ell': coeffs['ell'], 'frobeniusEigenvalue': coeffs['frobeniusEigenvalue'],
                         'generatorPolynomial': coeffs['generatorPolynomial'],
                         'targetPolynomial': coeffs['targetPolynomial'], 'knownScalar': coeffs['knownScalar']}
        if domain is not None and domain != currentDomain:
            raise ValueError('table domains do not match')
        domain = currentDomain
        h, payloadHash = manifest['branches'], manifest['payloadSha256']
        identity = 'ecc2k130-synthetic-pairs-h%d-v1' % h
        prefix = 'h%d/%s' % (h, payloadHash)
        publicMeta = {'schema': 'ecc2k-public-pair-table-v1', 'id': identity, 'domain': domain,
                      'scope': manifest['scope'], 'branches': h, 'entries': manifest['entries'],
                      'signedDirections': manifest['signedDirections'], 'bytes': manifest['bytes'],
                      'payloadSha256': payloadHash, 'encoding': manifest['encoding'],
                      'layout': manifest['layout'], 'directionLayout': manifest['directionLayout'],
                      'runtimeStatus': 'pair-sums-only', 'validation': manifest['validation'],
                      'limitations': manifest['limitations'], 'sourceSha256': manifest['sourceSha256']}
        publicPath = destination / prefix / 'table.json'
        publicPath.parent.mkdir(parents=True, exist_ok=True)
        publicPath.write_text(json.dumps(publicMeta, indent=2) + '\n')
        files = []
        for name in ('pairs.bin', 'directions.bin', 'coefficients.json', 'table.json'):
            path = publicPath if name == 'table.json' else source / name
            if name == 'pairs.bin':
                size, checksum = manifest['bytes'], payloadHash
            elif name == 'table.json':
                size, checksum = path.stat().st_size, table_store.digest(path)
            else:
                size, checksum = manifest['files'][name]['bytes'], manifest['files'][name]['sha256']
                if path.exists() and table_store.digest(path) != checksum:
                    raise ValueError('metadata/direction checksum mismatch')
            # `prepare` is useful in source-only CI where the 20/81 GB payloads
            # intentionally are not checked out. `publish` still hashes a
            # missing remote object's complete local source before upload.
            if path.exists():
                if path.stat().st_size != size:
                    raise ValueError('source file size differs from manifest')
            elif name.endswith('.json'):
                raise ValueError('required source file is missing: ' + str(path))
            item = {'name': name, 'key': prefix + '/' + name, 'bytes': size, 'sha256': checksum}
            files.append(item); uploads.append({'source': str(path.resolve()), **item})
        artifacts.append({'id': identity, 'branches': h, 'signedDirections': manifest['signedDirections'],
                          'entries': manifest['entries'], 'entryBytes': 36,
                          'runtimeStatus': 'pair-sums-only', 'generationBudgetBytes': manifest['budgetBytes'],
                          'files': files})
    catalog = {'schema': table_store.SCHEMA, 'scope': 'synthetic-precomputation-only',
               'domain': domain, 'artifacts': artifacts}
    table_store.validate_catalog(catalog)
    catalogPath = destination / 'catalog.json'
    catalogPath.write_text(json.dumps(catalog, indent=2) + '\n')
    (destination / 'upload-plan.local.json').write_text(json.dumps(uploads, indent=2) + '\n')
    return catalog, uploads, catalogPath


def aws(args, profile=None, region=None, allow_missing=False):
    command = ['aws']
    if profile: command += ['--profile', profile]
    if region: command += ['--region', region]
    command += args
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        if allow_missing and any(s in result.stderr for s in ('(404)', '(NoSuchKey)', '(NotFound)')):
            return None
        raise RuntimeError(result.stderr.strip() or 'AWS CLI failed')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def public_check_once(url, path, size):
    with urlopen(Request(url, method='HEAD'), timeout=30) as response:
        if int(response.headers.get('Content-Length', -1)) != size:
            raise ValueError('public object length mismatch')
    for start in sorted({0, max(0, size - 36)}):
        end = min(size - 1, start + 35)
        with urlopen(Request(url, headers={'Range': 'bytes=%d-%d' % (start, end)}), timeout=30) as response:
            if response.status != 206:
                raise ValueError('public endpoint does not support range downloads')
            remote = response.read(37)
        sourcePath = Path(path)
        if sourcePath.exists():
            with sourcePath.open('rb') as source:
                source.seek(start); expected = source.read(end - start + 1)
            if remote != expected:
                raise ValueError('public object sample mismatch')
        elif len(remote) != end - start + 1:
            raise ValueError('public object range length mismatch')


def public_check(url, path, size):
    for attempt in range(7):
        try:
            return public_check_once(url, path, size)
        except HTTPError as exc:
            if exc.code not in (403, 404, 429, 500, 502, 503, 504) or attempt == 6:
                raise
            delay = min(2 ** attempt, 16)
            print('public verification returned HTTP %d; retrying in %d s' % (exc.code, delay), flush=True)
            exc.close()
            time.sleep(delay)


def publish(destination, bucket, region, prefix, profile=None):
    if not bucket or '/' in bucket or not prefix.strip('/'):
        raise ValueError('bucket and nonempty object prefix are required')
    prefix = prefix.strip('/')
    # Fail before hashing/transferring large files if credentials are invalid.
    identity = aws(['sts', 'get-caller-identity'], profile, region)
    catalog, uploads, catalogPath = prepare(destination)
    base = 'https://%s.s3.%s.amazonaws.com/%s/' % (bucket, region, quote(prefix, safe='/'))
    catalog['publicBaseUrl'] = base
    catalogPath.write_text(json.dumps(catalog, indent=2) + '\n')
    reports = []
    # Sidecars first: verify anonymous public access before large transfers.
    for item in sorted(uploads, key=lambda f: f['bytes']):
        key = prefix + '/' + item['key']
        head = aws(['s3api', 'head-object', '--bucket', bucket, '--key', key], profile, region, True)
        if head is not None:
            if head.get('ContentLength') != item['bytes'] or head.get('Metadata', {}).get('sha256') != item['sha256']:
                raise ValueError('immutable S3 key exists with a different identity: ' + key)
            action = 'reused'
        else:
            print('verifying and uploading %s (%d bytes)' % (item['name'], item['bytes']), flush=True)
            if table_store.digest(item['source']) != item['sha256']:
                raise ValueError('local source checksum changed')
            aws(['s3', 'cp', item['source'], 's3://' + bucket + '/' + key,
                 '--only-show-errors', '--no-progress', '--sse', 'AES256',
                 '--checksum-algorithm', 'SHA256', '--metadata', 'sha256=' + item['sha256'],
                 '--cache-control', 'public,max-age=31536000,immutable',
                 '--content-type', 'application/json' if item['name'].endswith('.json') else 'application/octet-stream'], profile, region)
            action = 'uploaded'
            head = aws(['s3api', 'head-object', '--bucket', bucket, '--key', key], profile, region)
            if head.get('ContentLength') != item['bytes'] or head.get('Metadata', {}).get('sha256') != item['sha256']:
                raise ValueError('uploaded S3 object identity mismatch')
        url = base + quote(item['key'], safe='/')
        public_check(url, item['source'], item['bytes'])
        reports.append({'key': key, 'url': url, 'bytes': item['bytes'], 'sha256': item['sha256'],
                        'action': action, 'anonymousHeadAndRanges': True})
        print('public URL verified: ' + url, flush=True)
    # This discoverable catalog is published only after every payload is ready.
    catalogKey = prefix + '/catalog.json'
    aws(['s3', 'cp', str(catalogPath), 's3://' + bucket + '/' + catalogKey,
         '--only-show-errors', '--sse', 'AES256', '--content-type', 'application/json',
         '--cache-control', 'public,max-age=300', '--metadata', 'sha256=' + table_store.digest(catalogPath)], profile, region)
    catalogUrl = base + 'catalog.json'
    with urlopen(catalogUrl, timeout=30) as response:
        if response.read(table_store.MAX_CATALOG + 1) != catalogPath.read_bytes():
            raise ValueError('public catalog content mismatch')
    receipt = {'schema': 'ecc2k-table-publication-v1', 'catalogUrl': catalogUrl,
               'catalogSha256': table_store.digest(catalogPath), 'account': identity['Account'],
               'objects': reports, 'anonymousCatalogVerified': True}
    (Path(destination) / 'publication.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'publish'))
    parser.add_argument('--out', type=Path, default=ROOT / 'tables')
    parser.add_argument('--bucket')
    parser.add_argument('--region', default='us-west-2')
    parser.add_argument('--prefix', default='public/ecc2k130/synthetic-pairs/v1')
    parser.add_argument('--profile')
    args = parser.parse_args()
    if args.command == 'prepare':
        catalog, uploads, path = prepare(args.out)
        print(json.dumps({'catalog': str(path), 'artifacts': len(catalog['artifacts']),
                          'uploadBytes': sum(i['bytes'] for i in uploads)}, indent=2))
    else:
        if not args.bucket: parser.error('--bucket is required for publication')
        print(json.dumps(publish(args.out, args.bucket, args.region, args.prefix, args.profile), indent=2))


if __name__ == '__main__':
    main()
