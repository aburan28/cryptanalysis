#!/usr/bin/env python3
"""Run resumable synthetic Metal walk chunks and publish their DPs to S3.

Each chunk starts at the last acknowledged state. Distinguished-point records
are uploaded first, followed by a content-addressed state and manifest; only
then does latest.json advance. A crash can therefore repeat a chunk, but cannot
move the recovery boundary past records that were not uploaded.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import socket
import sys
import threading
import time
import uuid

from artifact_reference import Reference, STATE, REPORT, MASK
import run_walk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runner' / 'aws'))
import table_store
from worker import LocalStore, S3Slots, S3Store

SCHEMA = 'ecc2k130-synthetic-metal-continuous-v1'
WALK_ID = 'ecc2k130-synthetic-signed-frobenius-v1'
RECORD_FORMAT = 'artifact-dp-80-v1'
LEASE_SECONDS = 300
HEARTBEAT_SECONDS = 60


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ ', time.gmtime()) + message, flush=True)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def objectDigest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomicJson(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(str(temporary), str(path))


def atomicCopy(source, destination):
    destination = Path(destination)
    temporary = destination.with_name(destination.name + '.tmp')
    shutil.copyfile(str(source), str(temporary))
    os.replace(str(temporary), str(destination))


def safePrefix(value):
    value = value.strip('/')
    if (not value or not re.fullmatch(r'[A-Za-z0-9/_.-]+', value) or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('unsafe or empty storage prefix')
    return value


class WorkLock:
    def __init__(self, path):
        self.handle = open(path, 'w')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.handle.close()
            raise RuntimeError('another continuous walker owns this work directory')

    def close(self):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


class NoRemoteLease:
    lost = False

    def acquire(self):
        return

    def ensure(self):
        return

    def release(self):
        return


class S3RunLease:
    """One fixed conditional S3 lease for a run prefix."""
    def __init__(self, bucket, prefix, owner):
        self.slots = S3Slots(bucket, prefix)
        self.owner = owner
        self.lost = False
        self.error = None
        self.done = threading.Event()
        self.thread = None
        self.acquired = False

    def acquire(self):
        for _ in range(8):
            item, etag = self.slots._get(0)
            now = int(time.time())
            if item is not None and int(item.get('leaseUntil') or 0) > now:
                raise RuntimeError('this S3 run prefix already has an active owner')
            value = dict(item or {})
            value.update(owner=self.owner, state='active', claimedAt=now,
                         updatedAt=now, leaseUntil=now + LEASE_SECONDS,
                         host=socket.gethostname())
            ok = self.slots._put(0, value, create=item is None,
                                 ifMatch=etag if item is not None else None)
            if ok:
                self.acquired = True
                self.thread = threading.Thread(target=self._heartbeat, daemon=True)
                self.thread.start()
                return
        raise RuntimeError('could not acquire the S3 run lease')

    def _heartbeat(self):
        while not self.done.wait(HEARTBEAT_SECONDS):
            try:
                now = int(time.time())
                ok = self.slots._modify(0, self.owner, lambda item: item.update(
                    updatedAt=now, leaseUntil=now + LEASE_SECONDS))
                if not ok:
                    raise RuntimeError('conditional heartbeat was rejected')
            except Exception as exc:
                self.error = exc
                self.lost = True
                return

    def ensure(self):
        if self.lost:
            raise RuntimeError('S3 run lease lost; refusing to publish: %s' %
                               type(self.error).__name__)

    def release(self):
        if not self.acquired:
            return
        self.done.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.lost:
            return
        try:
            self.slots._modify(0, self.owner, lambda item: item.update(
                state='idle', leaseUntil=0, updatedAt=int(time.time())))
        except Exception as exc:
            log('lease release failed: %s' % type(exc).__name__)


class StopState:
    def __init__(self):
        self.stopping = False

    def onSignal(self, number, frame):
        if not self.stopping:
            log('signal %d: finishing the current chunk and its upload' % number)
        self.stopping = True


def sourceHashes():
    paths = [ROOT / 'metal' / name for name in
             ('artifact_walk.metal', 'artifact_walk.mm', 'artifact_reference.py')]
    paths += [ROOT / 'scripts' / 'mslgen.py', ROOT / 'research' / 'step_table' / 'pack.py',
              ROOT / 'research' / 'step_table' / 'table.py', ROOT / 'codegen' / 'field.py',
              ROOT / 'codegen' / 'curves.py', ROOT / 'generated' / 'eccF131.h']
    paths += sorted((ROOT / 'include').glob('*.h')) + sorted((ROOT / 'include').glob('*.cuh'))
    return {str(path.relative_to(ROOT)): table_store.digest(path) for path in paths}


def runtimeConfig(args):
    return {'lanes': args.lanes, 'cycles': args.cycles, 'launches': args.chunk_launches,
            'branches': args.branches, 'dpCap': args.dp_cap, 'batch': args.batch,
            'dpWeight': args.dp_weight, 'seed': args.seed,
            'seedStride': args.lanes * args.shard_count,
            'progressEvery': args.progress_every}


def laneSeed(args, lane):
    return args.seed + args.shard_index + lane * args.shard_count


def prepareInput(args):
    config = runtimeConfig(args)
    catalog, base = table_store.load_catalog(args.catalog)
    entry = next(value for value in catalog['artifacts'] if value['branches'] == args.branches)
    root = args.work / 'input'
    if not root.exists():
        reference = run_walk.prepare(root, entry, catalog, base, args.artifact_dir, config)
    else:
        expected = {item['name']: item for item in entry['files']}
        for name in ('directions.bin', 'coefficients.json'):
            path = root / name
            item = expected[name]
            if (not path.is_file() or path.stat().st_size != item['bytes'] or
                    table_store.digest(path) != item['sha256']):
                raise ValueError('existing input artifact identity mismatch: ' + name)
        coefficients = json.loads((root / 'coefficients.json').read_text())
        for key in ('ell', 'frobeniusEigenvalue', 'generatorPolynomial',
                    'targetPolynomial', 'knownScalar'):
            if coefficients.get(key) != catalog['domain'].get(key):
                raise ValueError('existing artifact does not match the catalog domain')
        reference = Reference((root / 'directions.bin').read_bytes(), args.branches)
        if (not (root / 'selector.bin').is_file() or
                (root / 'selector.bin').read_bytes() != reference.constants()):
            raise ValueError('existing selector constants differ from the artifact')
        for name in ('arithmetic-in.bin', 'arithmetic-expected.bin'):
            if not (root / name).is_file() or not (root / name).stat().st_size:
                raise ValueError('existing input is incomplete: ' + name)
        (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    # Always reconstruct the fresh boundary before considering remote state.
    # This prevents an unacknowledged local chunk from becoming a checkpoint.
    initial = b''.join(
        reference.serialize(reference.initial(laneSeed(args, lane)))
        for lane in range(args.lanes))
    (root / 'initial.bin').write_bytes(initial)
    (root / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    return root, reference, catalog, entry


def campaignDescription(args, inputRoot, catalog, entry):
    coefficients = json.loads((inputRoot / 'coefficients.json').read_text())
    artifacts = {
        'catalogSchema': catalog['schema'], 'artifactId': entry['id'],
        'directionsSha256': table_store.digest(inputRoot / 'directions.bin'),
        'coefficientsSha256': table_store.digest(inputRoot / 'coefficients.json'),
        'selectorSha256': table_store.digest(inputRoot / 'selector.bin')}
    walk = {
        'algorithm': WALK_ID, 'recordFormat': RECORD_FORMAT,
        'fieldDegree': 131, 'branches': args.branches, 'dpWeight': args.dp_weight,
        'selectorSalt': 20260921, 'knownScalar': coefficients['knownScalar'],
        'generatorPolynomial': coefficients['generatorPolynomial'],
        'targetPolynomial': coefficients['targetPolynomial'], 'artifacts': artifacts}
    walkIdentity = objectDigest(walk)
    executable = ROOT / 'build' / 'metal-artifact-walk'
    if not executable.is_file():
        raise ValueError('build first: make -C %s' % (ROOT / 'metal'))
    run = {'walkIdentity': walkIdentity, 'runId': args.run_id,
           'seedBase': args.seed, 'shardCount': args.shard_count,
           'shardIndex': args.shard_index,
           'seedLayout': 'residue-v1',
           'initialSeed': laneSeed(args, 0),
           'initialStateSha256': table_store.digest(inputRoot / 'initial.bin'),
           'lanes': args.lanes, 'seedStride': args.lanes * args.shard_count,
           'batch': args.batch,
           'binarySha256': table_store.digest(executable),
           'sourceSha256': sourceHashes()}
    runIdentity = objectDigest(run)
    return {'schema': SCHEMA, 'scope': 'public synthetic unknown-scalar control',
            'walkId': WALK_ID, 'recordFormat': RECORD_FORMAT,
            'walkIdentity': walkIdentity, 'runIdentity': runIdentity,
            'runId': args.run_id, 'walk': walk, 'run': run}


def storeFor(args, prefix):
    if args.local_store:
        root = args.local_store.resolve() / prefix
        root.mkdir(parents=True, exist_ok=True)
        return LocalStore(str(root)), NoRemoteLease(), str(root)
    bucket = args.bucket or os.environ.get('ECC_BUCKET')
    if not bucket:
        raise ValueError('--bucket or ECC_BUCKET is required without --local-store')
    store = S3Store(bucket, prefix)
    owner = '%s:%d:%s' % (socket.gethostname(), os.getpid(), uuid.uuid4().hex)
    return store, S3RunLease(bucket, prefix, owner), 's3://%s/%s' % (bucket, prefix)


def readStoreJson(store, key, work):
    target = work / ('.download-' + uuid.uuid4().hex + '.json')
    try:
        if not store.get(key, str(target)):
            return None
        return json.loads(target.read_text())
    finally:
        if target.exists():
            target.unlink()


def ensureCampaign(store, campaign, work):
    local = work / 'campaign.json'
    if local.exists() and json.loads(local.read_text()) != campaign:
        raise ValueError('work directory is bound to a different walk/run identity')
    atomicJson(local, campaign)
    exists = store.exists('campaign.json')
    if not exists and store.create(str(local), 'campaign.json'):
        return
    if exists or store.exists('campaign.json'):
        remote = readStoreJson(store, 'campaign.json', work)
        if remote != campaign:
            raise ValueError('storage prefix is bound to a different walk/run identity')
        return
    raise RuntimeError('campaign object was not created and is still missing')


def stateRows(data, lanes):
    if len(data) != lanes * STATE.size:
        raise ValueError('checkpoint has the wrong state size')
    rows = [STATE.unpack_from(data, lane * STATE.size) for lane in range(lanes)]
    for row in rows:
        if row[13] not in (0, 1, 2, 3) or row[4] & ~7 or row[9] & ~7:
            raise ValueError('checkpoint contains an invalid lane state')
    totals = {'walkUpdates': sum(row[16] for row in rows),
              'seedAdditions': sum(row[17] for row in rows),
              'dpRecords': sum(row[20] for row in rows),
              'haltedLanes': sum(row[13] == 2 for row in rows),
              'exhaustedLanes': sum(row[13] == 3 for row in rows)}
    return rows, totals


def reportRows(data, lanes, branches):
    if len(data) % REPORT.size:
        raise ValueError('DP delta ends in a partial record')
    records = [data[offset:offset + REPORT.size]
               for offset in range(0, len(data), REPORT.size)]
    perLane = [0] * lanes
    for record in records:
        row = REPORT.unpack(record)
        lane = row[2]
        if (lane >= lanes or row[-1] != 0 or row[7] & ~7 or row[12] & ~7 or
                any(value != 0xffffffff and value >= 262 * branches for value in row[13:16])):
            raise ValueError('DP delta contains an invalid record')
        perLane[lane] += 1
    return records, perLane


def verifyTransition(reference, before, after, records, config, count, sequence):
    if not count:
        return 0
    lanes = config['lanes']
    rng = random.Random(0x636f6e74696e756f ^ sequence)
    if count == 1:
        selected = [rng.randrange(lanes)]
    else:
        selected = [0, lanes - 1]
        choices = [lane for lane in range(1, lanes - 1)]
        selected += rng.sample(choices, min(count - 2, len(choices)))
    byLane = {}
    for raw in records:
        lane = REPORT.unpack(raw)[2]
        byLane.setdefault(lane, []).append(raw)
    cycles = config['cycles'] * config['launches']
    for lane in selected:
        old = before[lane * STATE.size:(lane + 1) * STATE.size]
        expected, expectedReports = reference.replay_from(
            old, lane, lanes, cycles, config['dpWeight'],
            config.get('seedStride', lanes))
        actual = after[lane * STATE.size:(lane + 1) * STATE.size]
        if actual != expected:
            raise ValueError('CPU/GPU resumed-state mismatch at lane %d' % lane)
        if sorted(byLane.get(lane, [])) != sorted(expectedReports):
            raise ValueError('CPU/GPU resumed-report mismatch at lane %d' % lane)
    return len(selected)


def validateChunk(before, state, reports, native, config, reference, verifyLanes, sequence):
    run_walk.validateRates(native)
    beforeRows, old = stateRows(before, config['lanes'])
    afterRows, new = stateRows(state, config['lanes'])
    records, perLane = reportRows(reports, config['lanes'], config['branches'])
    for lane, (oldRow, newRow) in enumerate(zip(beforeRows, afterRows)):
        if any(newRow[index] < oldRow[index] for index in (16, 17, 20)):
            raise ValueError('lane counters moved backwards at lane %d' % lane)
        if newRow[20] - oldRow[20] != perLane[lane]:
            raise ValueError('lane report count differs from checkpoint at lane %d' % lane)
    delta = {key: new[key] - old[key] for key in
             ('walkUpdates', 'seedAdditions', 'dpRecords')}
    for key in ('walkUpdates', 'seedAdditions', 'dpRecords'):
        if native.get(key) != delta[key]:
            raise ValueError('native delta accounting mismatch: ' + key)
    for key in ('haltedLanes', 'exhaustedLanes'):
        if native.get(key) != new[key]:
            raise ValueError('native final-state accounting mismatch: ' + key)
    if (native.get('groupOperations') != delta['walkUpdates'] + delta['seedAdditions'] or
            native.get('droppedRecords') != 0 or native.get('lanes') != config['lanes'] or
            native.get('branches') != config['branches']):
        raise ValueError('native geometry/group-operation accounting mismatch')
    checked = verifyTransition(reference, before, state, records, config,
                               verifyLanes, sequence)
    return old, new, delta, checked


def makePending(args, inputRoot, reference, campaign, sequence):
    pending = args.work / 'pending'
    if pending.exists():
        raise RuntimeError('pending chunk must be recovered before another launch')
    temporary = args.work / ('.pending-' + uuid.uuid4().hex)
    temporary.mkdir()
    try:
        before = (inputRoot / 'initial.bin').read_bytes()
        executable = ROOT / 'build' / 'metal-artifact-walk'
        if not executable.is_file():
            raise ValueError('build first: make -C %s' % (ROOT / 'metal'))
        native = run_walk.runNative(executable, inputRoot, temporary,
                                    temporary / 'native.log', shieldSignals=True)
        state = (temporary / 'state.bin').read_bytes()
        reports = (temporary / 'reports.bin').read_bytes()
        config = runtimeConfig(args)
        old, cumulative, delta, checked = validateChunk(
            before, state, reports, native, config, reference,
            args.verify_lanes, sequence)
        stateSha = hashlib.sha256(state).hexdigest()
        reportSha = hashlib.sha256(reports).hexdigest()
        stateKey = 'checkpoints/state-%012d-%s.bin' % (sequence, stateSha)
        dpKey = ('dp/chunk-%012d-%s-%012d.bin' %
                 (sequence, reportSha, len(reports))) if reports else None
        manifest = {
            'schema': SCHEMA, 'runIdentity': campaign['runIdentity'],
            'walkIdentity': campaign['walkIdentity'], 'sequence': sequence,
            'previousStateSha256': hashlib.sha256(before).hexdigest(),
            'state': {'key': stateKey, 'sha256': stateSha, 'bytes': len(state)},
            'distinguishedPoints': {'key': dpKey, 'sha256': reportSha,
                                    'bytes': len(reports),
                                    'records': len(reports) // REPORT.size,
                                    'recordBytes': REPORT.size,
                                    'recordFormat': RECORD_FORMAT},
            'work': {'cyclesPerLaunch': args.cycles,
                     'launches': args.chunk_launches,
                     'laneCycles': args.cycles * args.chunk_launches,
                     'delta': delta, 'startingTotals': old,
                     'verifiedLanes': checked},
            'cumulative': cumulative}
        manifestSha = objectDigest(manifest)
        manifestKey = 'manifests/chunk-%012d-%s.json' % (sequence, manifestSha)
        atomicJson(temporary / 'manifest.json', manifest)
        atomicJson(temporary / 'native.json', native)
        (temporary / 'manifest-key.txt').write_text(manifestKey + '\n')
        os.replace(str(temporary), str(pending))
        return pending
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def putImmutable(store, source, key, work):
    if store.create(str(source), key):
        return
    downloaded = work / ('.verify-' + uuid.uuid4().hex)
    try:
        if not store.get(key, str(downloaded)):
            raise RuntimeError('immutable object disappeared after create conflict')
        if (downloaded.stat().st_size != source.stat().st_size or
                table_store.digest(downloaded) != table_store.digest(source)):
            raise RuntimeError('immutable object key already contains different bytes')
    finally:
        if downloaded.exists():
            downloaded.unlink()


def validateManifest(manifest, campaign):
    if (manifest.get('schema') != SCHEMA or
            manifest.get('runIdentity') != campaign['runIdentity'] or
            manifest.get('walkIdentity') != campaign['walkIdentity'] or
            type(manifest.get('sequence')) is not int or manifest['sequence'] < 0):
        raise ValueError('chunk manifest identity/schema mismatch')
    sequence = manifest['sequence']
    state = manifest.get('state', {})
    points = manifest.get('distinguishedPoints', {})
    stateSha = state.get('sha256', '')
    pointSha = points.get('sha256', '')
    if (not re.fullmatch(r'[0-9a-f]{64}', stateSha) or
            not re.fullmatch(r'[0-9a-f]{64}', pointSha) or
            state.get('bytes') != campaign['run']['lanes'] * STATE.size or
            type(points.get('records')) is not int or points['records'] < 0 or
            points.get('recordBytes') != REPORT.size or
            points.get('bytes') != points['records'] * REPORT.size or
            points.get('recordFormat') != RECORD_FORMAT or
            not re.fullmatch(r'[0-9a-f]{64}', manifest.get('previousStateSha256', ''))):
        raise ValueError('chunk manifest has invalid state/DP metadata')
    expectedState = 'checkpoints/state-%012d-%s.bin' % (sequence, stateSha)
    expectedPoints = ('dp/chunk-%012d-%s-%012d.bin' %
                      (sequence, pointSha, points['bytes'])) if points['records'] else None
    if state.get('key') != expectedState or points.get('key') != expectedPoints:
        raise ValueError('chunk manifest has invalid content-addressed keys')
    work = manifest.get('work', {})
    old = work.get('startingTotals', {})
    delta = work.get('delta', {})
    cumulative = manifest.get('cumulative', {})
    for name in ('walkUpdates', 'seedAdditions', 'dpRecords'):
        if (type(old.get(name)) is not int or type(delta.get(name)) is not int or
                type(cumulative.get(name)) is not int or old[name] < 0 or delta[name] < 0 or
                cumulative[name] != old[name] + delta[name]):
            raise ValueError('chunk manifest counters are inconsistent')
    if delta['dpRecords'] != points['records']:
        raise ValueError('chunk manifest DP count is inconsistent')
    return 'manifests/chunk-%012d-%s.json' % (sequence, objectDigest(manifest))


def publishPending(store, lease, pending, inputRoot, campaign, work, storeUrl):
    manifest = json.loads((pending / 'manifest.json').read_text())
    native = json.loads((pending / 'native.json').read_text())
    expectedManifestKey = validateManifest(manifest, campaign)
    stateInfo = manifest['state']
    dpInfo = manifest['distinguishedPoints']
    state = pending / 'state.bin'
    reports = pending / 'reports.bin'
    if (state.stat().st_size != stateInfo['bytes'] or
            table_store.digest(state) != stateInfo['sha256'] or
            reports.stat().st_size != dpInfo['bytes'] or
            table_store.digest(reports) != dpInfo['sha256']):
        raise ValueError('pending chunk bytes differ from its manifest')
    lease.ensure()
    if dpInfo['key']:
        putImmutable(store, reports, dpInfo['key'], work)
    lease.ensure()
    putImmutable(store, state, stateInfo['key'], work)
    manifestKey = (pending / 'manifest-key.txt').read_text().strip()
    if manifestKey != expectedManifestKey:
        raise ValueError('pending manifest key does not match its bytes')
    putImmutable(store, pending / 'manifest.json', manifestKey, work)
    lease.ensure()
    latest = {'schema': SCHEMA, 'runIdentity': campaign['runIdentity'],
              'walkIdentity': campaign['walkIdentity'],
              'sequence': manifest['sequence'], 'manifestKey': manifestKey,
              'state': stateInfo, 'cumulative': manifest['cumulative'],
              'lastPerformance': native,
              'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    atomicJson(pending / 'latest.json', latest)
    store.put(str(pending / 'latest.json'), 'latest.json')
    atomicCopy(state, inputRoot / 'initial.bin')
    atomicJson(work / 'local-latest.json', latest)
    shutil.rmtree(pending)
    log('published chunk %d: %d DP records, %d cumulative walk iterations -> %s/latest.json' %
        (manifest['sequence'], dpInfo['records'],
         manifest['cumulative']['walkUpdates'], storeUrl))
    return manifest['sequence'] + 1, latest


def restoreLatest(store, inputRoot, campaign, work):
    latest = readStoreJson(store, 'latest.json', work)
    if latest is None:
        stateRows((inputRoot / 'initial.bin').read_bytes(), campaign['run']['lanes'])
        return 0, None
    if (latest.get('schema') != SCHEMA or
            latest.get('runIdentity') != campaign['runIdentity'] or
            latest.get('walkIdentity') != campaign['walkIdentity'] or
            type(latest.get('sequence')) is not int or latest['sequence'] < 0):
        raise ValueError('remote latest checkpoint identity/schema mismatch')
    manifestKey = latest.get('manifestKey', '')
    manifest = readStoreJson(store, manifestKey, work) if re.fullmatch(
        r'manifests/chunk-[0-9]{12}-[0-9a-f]{64}\.json', manifestKey) else None
    if manifest is None or validateManifest(manifest, campaign) != manifestKey:
        raise ValueError('remote latest manifest is missing or invalid')
    if (manifest['sequence'] != latest['sequence'] or
            manifest['state'] != latest.get('state') or
            manifest['cumulative'] != latest.get('cumulative')):
        raise ValueError('remote latest pointer differs from its manifest')
    points = manifest['distinguishedPoints']
    if points['key'] and not store.exists(points['key']):
        raise ValueError('remote latest DP delta object is missing')
    info = latest.get('state', {})
    key = info.get('key', '')
    if not re.fullmatch(r'checkpoints/state-[0-9]{12}-[0-9a-f]{64}\.bin', key):
        raise ValueError('remote latest checkpoint key is invalid')
    target = work / ('.resume-' + uuid.uuid4().hex)
    try:
        if not store.get(key, str(target)):
            raise ValueError('remote latest checkpoint object is missing')
        if (target.stat().st_size != info.get('bytes') or
                table_store.digest(target) != info.get('sha256')):
            raise ValueError('remote checkpoint bytes do not match latest.json')
        stateRows(target.read_bytes(), campaign['run']['lanes'])
        atomicCopy(target, inputRoot / 'initial.bin')
    finally:
        if target.exists():
            target.unlink()
    log('resumed after chunk %d at %d cumulative walk iterations' %
        (latest['sequence'], latest['cumulative']['walkUpdates']))
    return latest['sequence'] + 1, latest


def pendingSequence(pending):
    manifest = json.loads((pending / 'manifest.json').read_text())
    return manifest['sequence'], manifest


def recoverPending(store, lease, args, inputRoot, campaign, sequence,
                   latest, storeUrl, stop):
    pending = args.work / 'pending'
    if not pending.exists():
        return sequence, latest
    pendingSeq, manifest = pendingSequence(pending)
    currentSha = table_store.digest(inputRoot / 'initial.bin')
    if pendingSeq == sequence:
        if manifest['previousStateSha256'] != currentSha:
            raise ValueError('pending chunk does not start at the recovery boundary')
        log('recovering unacknowledged local chunk %d before launching more work' % pendingSeq)
        return publishWithRetry(store, lease, pending, inputRoot, campaign,
                                args, storeUrl, stop)
    if (pendingSeq + 1 == sequence and
            manifest['state']['sha256'] == currentSha):
        log('discarding local chunk %d already acknowledged by latest.json' % pendingSeq)
        shutil.rmtree(pending)
        return sequence, latest
    raise ValueError('pending chunk sequence does not match the recovery boundary')


def publishWithRetry(store, lease, pending, inputRoot, campaign, args,
                     storeUrl, stop):
    attempts = 0
    delay = 2
    while True:
        try:
            return publishPending(store, lease, pending, inputRoot, campaign,
                                  args.work, storeUrl)
        except ValueError:
            raise
        except Exception as exc:
            attempts += 1
            if lease.lost:
                raise
            if stop.stopping or (args.upload_retries and attempts > args.upload_retries):
                raise RuntimeError('upload incomplete; pending chunk retained (%s)' %
                                   type(exc).__name__) from None
            detail = ' '.join(str(exc).split())[:300] or type(exc).__name__
            log('upload attempt %d failed: %s; retrying in %d s' %
                (attempts, detail, delay))
            deadline = time.monotonic() + delay
            while time.monotonic() < deadline and not stop.stopping:
                time.sleep(min(0.25, deadline - time.monotonic()))
            delay = min(60, delay * 2)


def run(args):
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    lock = WorkLock(str(args.work / '.lock'))
    stop = StopState()
    signal.signal(signal.SIGINT, stop.onSignal)
    signal.signal(signal.SIGTERM, stop.onSignal)
    prefix = safePrefix(args.prefix or
                        'campaigns/ecc2k130-synthetic-metal-h%d-v1/%s' %
                        (args.branches, args.run_id))
    store, lease, storeUrl = storeFor(args, prefix)
    try:
        inputRoot, reference, catalog, entry = prepareInput(args)
        campaign = campaignDescription(args, inputRoot, catalog, entry)
        ensureCampaign(store, campaign, args.work)
        lease.acquire()
        sequence, latest = restoreLatest(store, inputRoot, campaign, args.work)
        sequence, latest = recoverPending(store, lease, args, inputRoot,
                                          campaign, sequence, latest,
                                          storeUrl, stop)
        completed = 0
        while not stop.stopping and (not args.max_chunks or completed < args.max_chunks):
            lease.ensure()
            pending = makePending(args, inputRoot, reference, campaign, sequence)
            sequence, latest = publishWithRetry(
                store, lease, pending, inputRoot, campaign, args, storeUrl, stop)
            completed += 1
            cumulative = latest['cumulative']
            if cumulative['haltedLanes'] + cumulative['exhaustedLanes'] == args.lanes:
                log('all lanes are terminal; continuous run is complete')
                break
        if stop.stopping:
            log('continuous run stopped cleanly at the acknowledged checkpoint')
        elif args.max_chunks:
            log('bounded rehearsal completed %d chunk(s)' % completed)
        return 0
    finally:
        lease.release()
        lock.close()


def parseArgs():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True,
                        help='durable local work directory')
    parser.add_argument('--run-id', required=True,
                        help='unique name for this seed stream and checkpoint')
    parser.add_argument('--bucket', help='S3 bucket; defaults to ECC_BUCKET')
    parser.add_argument('--prefix', help='complete S3 prefix; defaults to an isolated synthetic run prefix')
    parser.add_argument('--local-store', type=Path,
                        help='directory-backed rehearsal store instead of S3')
    parser.add_argument('--artifact-dir', type=Path,
                        help='validated local pair-table directory; only compact files are copied')
    parser.add_argument('--catalog')
    parser.add_argument('--branches', type=int, choices=(128, 256), default=128)
    parser.add_argument('--lanes', type=int, default=128)
    parser.add_argument('--cycles', type=int, default=64)
    parser.add_argument('--chunk-launches', type=int, default=256,
                        help='bounded launches between durable uploads')
    parser.add_argument('--batch', type=int, choices=(1, 4, 8, 16, 32), default=16)
    parser.add_argument('--dp-weight', type=int, default=32)
    parser.add_argument('--dp-cap', type=int, default=65536)
    parser.add_argument('--seed', type=int, default=20260921)
    parser.add_argument('--shard-count', type=int, default=1,
                        help='total coordinated seed partitions')
    parser.add_argument('--shard-index', type=int, default=0,
                        help='this process partition, from 0 to shard-count - 1')
    parser.add_argument('--verify-lanes', type=int, default=0,
                        help='independently replay this many lanes in every chunk')
    parser.add_argument('--progress-every', type=int, default=16)
    parser.add_argument('--max-chunks', type=int, default=0,
                        help='0 runs until a signal; positive values are rehearsals')
    parser.add_argument('--upload-retries', type=int, default=0,
                        help='0 retries forever; a signal leaves the pending chunk local')
    args = parser.parse_args()
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', args.run_id) or
            not 1 <= args.lanes <= 65536 or not 1 <= args.cycles <= 128 or
            not 1 <= args.chunk_launches <= 10000 or not -1 <= args.dp_weight <= 130 or
            not 1 <= args.dp_cap <= 1000000 or not 0 <= args.seed <= MASK or
            not 1 <= args.shard_count or not 0 <= args.shard_index < args.shard_count or
            args.lanes * args.shard_count > 0xffffffff or
            laneSeed(args, args.lanes - 1) > MASK or
            not 0 <= args.verify_lanes <= args.lanes or args.progress_every < 1 or
            args.dp_cap * args.chunk_launches * REPORT.size > 4 * 1024 ** 3 or
            args.max_chunks < 0 or args.upload_retries < 0):
        parser.error('invalid run ID or workload/retry bounds')
    if args.local_store and args.bucket:
        parser.error('--local-store and --bucket are mutually exclusive')
    return args


if __name__ == '__main__':
    try:
        sys.exit(run(parseArgs()))
    except Exception as exc:
        log('fatal: %s' % exc)
        sys.exit(1)
