"""Append-only, hash-chained report checkpoints; linear work in completed groups.

Immutable metadata is written once. Only the active row, new candidates and
small mutable report fields are checkpointed. A final aggregate is written once.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path

MUTABLE = ('status','host','admission','interruption','memory','timing_qualification')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Journal:
    def __init__(self, output):
        self.output = Path(output)
        self.path = Path(str(output)+'.journal')
        self.compressed = Path(str(self.path)+'.gz')
        if any(p.exists() for p in (self.output, self.path, self.compressed)):
            raise FileExistsError('existing report or journal cannot be overwritten')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open('xb')
        self.previous, self.count = '0'*64, 0
        self.candidates, self.last_row, self.closed = {}, -1, False
        self.bytes_written = 0

    def _append(self, update):
        body = {'sequence': self.count, 'previous': self.previous, 'update': update}
        payload = encode(body)
        digest = hashlib.sha256(payload).hexdigest()
        data = digest.encode()+b' '+payload+b'\n'
        try:
            self.stream.write(data)
            self.stream.flush()
            os.fsync(self.stream.fileno())
        except BaseException:
            # Never append another record with the same sequence after an
            # ambiguous write. The intact prefix remains recoverable.
            self.close()
            raise
        self.bytes_written += len(data)
        self.previous, self.count = digest, self.count+1

    def checkpoint(self, report):
        if self.closed:
            raise RuntimeError('closed journal')
        if self.count == 0:
            self._append({'kind':'header', 'schema':'round22-checkpoints/1',
                          'report':{k:v for k,v in report.items() if k not in ('rows','candidates')}})
        row_index = len(report['rows'])-1
        if row_index not in (self.last_row, self.last_row+1):
            raise ValueError('checkpoint each group before starting the next')
        digests = {k:hashlib.sha256(encode(v)).hexdigest() for k,v in report['candidates'].items()}
        if any(digests.get(k) != v for k,v in self.candidates.items()):
            raise ValueError('candidate manifest mutated or removed')
        new = {k:v for k,v in report['candidates'].items() if k not in self.candidates}
        self._append({'kind':'checkpoint', 'state':{k:report[k] for k in MUTABLE if k in report},
                      'candidates':new, 'row_index':row_index,
                      'row':report['rows'][-1] if report['rows'] else None})
        self.candidates.update(digests)
        self.last_row = row_index

    def finish(self, report):
        self.checkpoint(report)
        self.stream.close()
        self.closed = True
        temporary = Path(str(self.output)+'.tmp')
        temporary.write_bytes(gzip.compress(encode(report), compresslevel=1, mtime=0))
        temporary.replace(self.output)
        # Preserve the complete journal; compression changes storage only.
        compressed_tmp = Path(str(self.compressed)+'.tmp')
        with self.path.open('rb') as source, compressed_tmp.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=1, mtime=0) as target:
                while chunk := source.read(1 << 20):
                    target.write(chunk)
        compressed_tmp.replace(self.compressed)
        self.path.unlink()

    def close(self):
        if not self.closed:
            self.stream.close()
            self.closed = True


def recover(path):
    """Read checkpoints without executing snapshots; never promote partial work."""
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    previous, count, report, truncated = '0'*64, 0, None, False
    with opener(path, 'rb') as stream:
        for line in stream:
            if not line.endswith(b'\n'):
                truncated = True
                break
            digest, separator, payload = line[:-1].partition(b' ')
            if not separator or hashlib.sha256(payload).hexdigest().encode() != digest:
                raise ValueError('journal checksum mismatch')
            body = json.loads(payload)
            if body['sequence'] != count or body['previous'] != previous:
                raise ValueError('journal sequence/chain mismatch')
            update = body['update']
            if count == 0:
                if update['kind'] != 'header' or update['schema'] != 'round22-checkpoints/1':
                    raise ValueError('journal header')
                report = update['report']
                report.update(rows=[], candidates={})
            else:
                if update['kind'] != 'checkpoint':
                    raise ValueError('journal checkpoint')
                report.update(update['state'])
                for cid, manifest in update['candidates'].items():
                    if cid in report['candidates']:
                        raise ValueError('candidate mutation')
                    report['candidates'][cid] = manifest
                index, row = update['row_index'], update['row']
                if index == -1:
                    if row is not None or report['rows']:
                        raise ValueError('empty checkpoint')
                elif index == len(report['rows']):
                    report['rows'].append(row)
                elif index == len(report['rows'])-1:
                    old = report['rows'][index]
                    if (old['workload_id'], old['repetition']) != (row['workload_id'],row['repetition']):
                        raise ValueError('group identity changed')
                    report['rows'][index] = row
                else:
                    raise ValueError('nonsequential group checkpoint')
            previous, count = digest.decode(), count+1
    if truncated and report is not None:
        report.update(status='INTERRUPTED',
                      timing_qualification={**report.get('timing_qualification',{}), 'eligible':False},
                      interruption='truncated trailing journal record')
    return report, {'records':count, 'truncated_tail':truncated, 'final_sha256':previous}
