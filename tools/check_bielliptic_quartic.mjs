// JSON/identity/exit-status checks only; all mathematical verification is native.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';

const [binary, crate] = process.argv.slice(2);
assert.ok(binary && crate, 'usage: checker BINARY CRATE');
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
const canonical = (value) => {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
};
const invoke = (args, code = 0) => {
  const result = spawnSync(binary, args, { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 });
  assert.equal(result.error, undefined);
  assert.equal(result.status, code, result.stderr);
  return result;
};

invoke(['--help']);
const demonstration = invoke(['demo']);
const record = JSON.parse(demonstration.stdout);
assert.equal(record.schema, 'bielliptic-quartic-diagnostic/v1');
assert.equal(record.scope, 'tiny-prime-field-elliptic-norm-projection');
assert.equal(record.candidate_id, null);
assert.equal(record.curve_uid, `urn:ec-record:1:sha256:${digest(JSON.stringify(canonical(record.curve_record)))}`);
assert.equal(record.implementation.kernel_sha256, digest(readFileSync(join(crate, 'src/cryptanalysis/bielliptic_quartic.rs'))));
assert.equal(record.implementation.cli_sha256, digest(readFileSync(join(crate, 'src/bin/quartic_ic.rs'))));
assert.equal(record.collection.certificates_sha256, digest(JSON.stringify(record.certificates)));
assert.equal(record.collection.certified_relations, record.certificates.length);
assert.equal(record.collection.pair_trials, record.collection.unique_lines + record.collection.duplicate_lines);
assert.equal(record.collection.unique_lines, record.collection.certified_relations + record.collection.nonsplit_residuals);
assert.equal(record.collection.certified_relations, 79);
assert.equal(record.precomputation.matrix_rank, 11);
assert.equal(record.precomputation.matrix_columns, 11);
assert.equal(record.precomputation.usable_norm_images, 22);
assert.equal(record.precomputation.independent_line_rows, 10);
assert.equal(record.precomputation.replayed_factor_logs, 11);
assert.equal(record.precomputation.factor_base_sha256, digest(JSON.stringify(record.precomputation.factor_base)));
assert.equal(record.recovery.scalar, 17);
assert.equal(record.recovery.verified, true);
assert.deepEqual(record.recovery.target, [29, 42]);
assert.ok(Object.values(record.costs).every((value) => value === null));

// A supplied target follows exactly the same path as the fixture demonstration.
const supplied = invoke(['solve', '--p', '53', '--a', '2', '--b', '1', '--generator', '0,1', '--target', '29,42']);
assert.equal(supplied.stdout, demonstration.stdout);
const rankFailure = JSON.parse(invoke(['demo', '--max-pairs', '0'], 2).stdout);
assert.equal(rankFailure.recovery.status, 'rank_deficient');
assert.equal(rankFailure.recovery.scalar, null);
assert.equal(rankFailure.collection.budget_exhausted, true);
const pairFailure = JSON.parse(invoke(['demo', '--max-pairs', '989'], 2).stdout);
assert.equal(pairFailure.precomputation.complete, true);
assert.equal(pairFailure.collection.budget_exhausted, true);
assert.equal(pairFailure.recovery.status, 'pair_budget_exhausted');
assert.equal(pairFailure.recovery.scalar, null);
assert.equal(pairFailure.recovery.shifts_tested, 0);
const targetFailure = JSON.parse(invoke(['demo', '--max-shifts', '0'], 2).stdout);
assert.equal(targetFailure.recovery.status, 'target_budget_exhausted');
assert.equal(targetFailure.recovery.verified, false);
assert.equal(targetFailure.recovery.scalar, null);

for (const p of ['2', '3', '9', '263']) {
  assert.match(invoke(['collect', '--p', p, '--a', '0', '--b', '1'], 2).stderr, /UnsupportedField/);
}
assert.match(invoke(['collect', '--p', '53', '--a', '0', '--b', '0'], 2).stderr, /SingularCurve/);
assert.match(invoke(['demo', '--max-pairs', '65537'], 2).stderr, /InvalidBudget/);
assert.match(invoke(['demo', '--max-shifts', '513'], 2).stderr, /InvalidBudget/);
assert.match(invoke(['demo', '--p', '53'], 2).stderr, /fixed inputs/);
assert.match(invoke(['demo', '--max-pairs', '1', '--max-pairs', '2'], 2).stderr, /duplicate option/);
const collection = JSON.parse(invoke(['collect', '--p', '7', '--a', '0', '--b', '1']).stdout);
assert.equal(collection.status, 'collection_only');
assert.equal(collection.precomputation, null);
assert.equal(collection.recovery, null);
console.log('Quartic CLI replay, source/curve/certificate hashes, supplied target and failure gates: passed.');
