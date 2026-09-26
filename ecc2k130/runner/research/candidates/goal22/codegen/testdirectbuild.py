"""Exercise packed reducer/product build and result helpers without Modal or a GPU."""
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest

from benchreport import benchResult, bestResult, summarizeSamples

ROOT = Path(__file__).resolve().parents[1]


def nodes(path):
    return ast.parse((ROOT / path).read_text()).body


def execute(body, env):
    exec(compile(ast.Module(body=body, type_ignores=[]), 'actual-wrapper', 'exec'), env)


def function(name, env, path='modal_app.py'):
    node = next(n for n in nodes(path) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    execute([node], env)
    return env[name]


def assignment(name, env):
    node = next(n for n in nodes('modal_app.py') if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
    execute([node], env)


def environment(mode='0', generated='0', tile='0', clmad='0', weighted='0', compact='0', shared='0', square='0', karat='0'):
    env = dict(re=re, hashlib=hashlib, pathlib=SimpleNamespace(Path=Path),
               subprocess=subprocess, time=time, json=json, benchResult=benchResult,
               summarizeSamples=summarizeSamples, bestResult=bestResult,
               CUDA_VERSION='13.0.0', DEFAULT_GPU='RTX-PRO-6000', BAKED_ARCHES=('120',), REMOTE='/unused',
               print=lambda *a, **k: None,
               bakedIntact=[True], computeCapability=lambda: '120', gpuName=lambda: 'fixture GPU')
    for key in ('SINGLE_PRODUCT', 'CACHE_DENOM', 'BY_VALUE', 'POLY_CHAIN',
                'UNROLL_INV', 'PAIR_PRODUCTS', 'POLY_STATE'):
        env['PACKED_' + key] = '1'
    env.update(PACKED_PERM_SIGMA='3', PACKED_DIRECT_REDUCE=mode, PACKED_GENERATED_PRODUCT=generated, PACKED_STATE_TILE=tile, PACKED_CLMAD=clmad, PACKED_CLMAD_SQUARE=square, PACKED_KARAT3=karat, PACKED_WEIGHTED_PREFIX=weighted, PACKED_COMPACT_STATE=compact, PACKED_SHARED_SIGMA=shared, PACKED_TOP_CLMAD='0', WALK_TABLE='0', TABLE_PIVOT_BYTES='0')
    assignment('BAKED', env)
    return env


def raw(mode='0', generated='0', tile='0', clmad='0', weighted='0', compact='0', shared='0', square='0', karat='0'):
    return (f'packed direct reduction: {mode}\n'
            f'packed generated product: {generated}\n'
            f'packed state tile: {tile}\n'
            f'packed native carryless multiply: {clmad}\n'
            f'packed native carryless square: {square}\n'
            f'packed three-limb Karatsuba: {karat}\n'
            f'packed weighted prefix: {weighted}\n'
            f'packed compact state: {compact}\n'
            f'packed shared sigma: {shared}\n'
            f'packed top clmad: 0\n'
            'finished: 6000.000 M it/s, 0 distinguished points (0 verified against the reference, 0 dropped)\n')


class DirectBuildTests(unittest.TestCase):
    def test_environment_defaults_and_rejects_invalid_values(self):
        body = nodes('modal_app.py')
        index = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_DIRECT_REDUCE' for t in n.targets))
        for value in (None, '0', '1', '', '2', '-1', 'true'):
            env = dict(os=SimpleNamespace(environ={} if value is None else {'ECC_PACKED_DIRECT_REDUCE': value}))
            with self.subTest(value=value):
                if value in (None, '0', '1'):
                    execute(body[index:index + 2], env)
                    self.assertEqual(env['PACKED_DIRECT_REDUCE'], value or '0')
                else:
                    with self.assertRaises(ValueError):
                        execute(body[index:index + 2], env)

    def test_image_preserves_flag_and_bakes_matching_binary(self):
        class Image:
            def __init__(self):
                self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1'):
            env = environment(mode)
            image = Image()
            env.update(modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)),
                       GENCODE='fixture', LOCAL=ROOT)
            assignment('image', env)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_DIRECT_REDUCE'], mode)
            builds = [c for c in image.calls['run_commands'] if 'make gpu ' in c]
            self.assertEqual(len(builds), 1)
            self.assertIn('PACKED_DIRECT_REDUCE=' + mode, builds[0])
            self.assertEqual(env['BAKED']['packedDirectReduction'], mode == '1')

    def test_cache_mismatch_rebuilds_and_matching_bake_is_not_reused_afterward(self):
        env = environment('0')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        env['PACKED_DIRECT_REDUCE'] = '1'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_DIRECT_REDUCE=1', commands[-1])
        env['PACKED_DIRECT_REDUCE'] = '0'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_DIRECT_REDUCE=0', commands[-1])
        self.assertEqual(len(commands), 2)

    def test_rebuild_false_rejects_a_different_reducer(self):
        env = environment('0')
        env['PACKED_DIRECT_REDUCE'] = '1'
        run = function('runBench', env)
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            run(rebuild=False, packed=True)

    def test_result_gate_never_ranks_wrong_missing_duplicate_or_failed_identity(self):
        for mode in ('0', '1'):
            check = function('checkPackedReduction', environment(mode))
            good = benchResult('fixture', 0, raw(mode))
            self.assertTrue(check(good))
            self.assertEqual(good['packedDirectReduction'], mode == '1')
            for rc, output in [(0, raw(str(1 - int(mode)))), (0, raw(mode).split('\n', 1)[1]),
                               (0, raw(mode) + f'packed direct reduction: {mode}\n'),
                               (0, raw('2')), (1, raw(mode))]:
                sample = benchResult('fixture', rc, output)
                self.assertFalse(check(sample))
                self.assertEqual(sample['rate'], 0)
                self.assertFalse(summarizeSamples([good, sample])['valid'])

    def test_measurement_checks_packed_mode_but_preserves_other_backends(self):
        env = environment('1')
        env['sh'] = lambda *a, **k: (0, raw('0'))
        function('checkPackedReduction', env)
        measure = function('measureBench', env)
        self.assertFalse(measure(1, 1, 0, False, 1, packed=True)['valid'])
        self.assertTrue(measure(1, 1, 0, False, 1, packed=False)['valid'])

    def test_identity_and_compile_check_record_actual_requested_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in [('Makefile', ''), ('modal_app.py', ''), ('ecc2k130', 'fixture'),
                               ('generated/eccF131.h', 'LEAF = 66')]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            for mode in ('0', '1'):
                env = environment(mode)
                env.update(REMOTE=directory, sh=lambda *a, **k: (0, 'fixture'),
                           buildFor=lambda *a, **k: (True, 'built'))
                identity = function('benchmarkIdentity', env)
                self.assertEqual(identity(True)['packedDirectReduction'], mode == '1')
                self.assertIsNone(identity(False)['packedDirectReduction'])
                self.assertEqual(function('runCompileCheck', env)()['packedDirectReduction'], mode == '1')

    def test_bench_and_autotune_rows_retain_flag_without_changing_config_format(self):
        for mode in ('0', '1'):
            env = environment(mode)
            env.update(buildFor=lambda *a, **k: (True, 'built'),
                       benchmarkIdentity=lambda *a, **k: {},
                       measureBench=lambda *a, **k: dict(valid=True, rate=6000.0),
                       os=SimpleNamespace(makedirs=lambda *a, **k: None),
                       open=lambda *a, **k: io.StringIO(),
                       volume=SimpleNamespace(commit=lambda: None))
            bench = function('runBench', env)(rebuild=False, packed=True)
            self.assertEqual(bench['packedDirectReduction'], mode == '1')
            function('autotuneConfigs', env)
            tune = function('runAutotune', env)(configs='0:32:128:2', packed=True)
            self.assertEqual(tune['results'][0]['packedDirectReduction'], mode == '1')
            self.assertEqual(len(env['autotuneConfigs']('', '', '', '', '0:32:128:2')[0]), 7)

    def test_audit_forwards_flag_and_rejects_an_arithmetic_binary_with_wrong_mode(self):
        for mode in ('0', '1'):
            with tempfile.TemporaryDirectory() as directory:
                commands = []
                client = SimpleNamespace(**environment(mode))
                client.buildFor = lambda *a, **k: (True, 'built')
                client.benchmarkIdentity = lambda **k: {'packedDirectReduction': mode == '1'}
                client.volume = SimpleNamespace(commit=lambda: None)
                def run(command, **kwargs):
                    commands.append(command)
                    return SimpleNamespace(returncode=0, stdout='packed arithmetic direct reduction: '
                                           + str(1 - int(mode)) + '\n', stderr='')
                env = dict(client=client, re=re, json=json, time=time,
                           print=lambda *a, **k: None,
                           subprocess=SimpleNamespace(run=run),
                           Path=lambda path: Path(directory) / 'artifact')
                report = function('runAudit', env, 'packed_audit.py')()
                self.assertFalse(report['valid'])
                self.assertIn('reducer identity', report['error'])
                self.assertEqual(report['packedDirectReduction'], mode == '1')
                self.assertEqual(len(commands), 1)
                self.assertIn('PACKED_DIRECT_REDUCE=' + mode, commands[0])


class GeneratedProductBuildTests(unittest.TestCase):
    def test_environment_defaults_invalid_values_and_reducer_prerequisite(self):
        body = nodes('modal_app.py')
        index = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_GENERATED_PRODUCT' for t in n.targets))
        for direct in ('0', '1'):
            for value in (None, '0', '1', '', '2', '-1', 'true'):
                env = dict(PACKED_DIRECT_REDUCE=direct,
                           os=SimpleNamespace(environ={} if value is None else {'ECC_PACKED_GENERATED_PRODUCT': value}))
                with self.subTest(value=value, direct=direct):
                    if value in (None, '0') or value == '1' and direct == '1':
                        execute(body[index:index + 3], env)
                        self.assertEqual(env['PACKED_GENERATED_PRODUCT'], value or '0')
                    else:
                        with self.assertRaises(ValueError):
                            execute(body[index:index + 3], env)

    def test_image_preserves_generated_mode_and_default_cuda_version(self):
        class Image:
            def __init__(self):
                self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1'):
            env = environment('1', mode)
            image = Image()
            env.update(modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)),
                       GENCODE='fixture', LOCAL=ROOT)
            assignment('image', env)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_GENERATED_PRODUCT'], mode)
            self.assertEqual(image.calls['env'][0]['ECC_CUDA_VERSION'], env['CUDA_VERSION'])
            builds = [c for c in image.calls['run_commands'] if 'make gpu ' in c]
            self.assertEqual(len(builds), 1)
            self.assertIn('PACKED_GENERATED_PRODUCT=' + mode, builds[0])
            self.assertEqual(env['BAKED']['packedGeneratedProduct'], mode == '1')
        env = dict(os=SimpleNamespace(environ={}))
        assignment('CUDA_VERSION', env)
        self.assertEqual(env['CUDA_VERSION'], '12.8.1')

    def test_mode_change_rebuilds_and_cannot_reuse_a_stale_bake(self):
        env = environment('1', '0')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        env['PACKED_GENERATED_PRODUCT'] = '1'
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            function('runBench', env)(rebuild=False, packed=True)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_GENERATED_PRODUCT=1', commands[-1])
        env['PACKED_GENERATED_PRODUCT'] = '0'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_GENERATED_PRODUCT=0', commands[-1])
        self.assertEqual(len(commands), 2)
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            function('runBench', env)(rebuild=False, packed=True)

    def test_actual_runtime_flag_is_required_for_every_packed_sample(self):
        for mode in ('0', '1'):
            env = environment('1', mode)
            check = function('checkPackedReduction', env)
            good = benchResult('fixture', 0, raw('1', mode))
            self.assertTrue(check(good))
            self.assertEqual(good['expectedPackedGeneratedProduct'], mode == '1')
            self.assertEqual(good['packedGeneratedProduct'], mode == '1')
            bad = [raw('1', str(1 - int(mode))),
                   raw('1', mode).replace(f'packed generated product: {mode}\n', ''),
                   raw('1', mode) + f'packed generated product: {mode}\n', raw('1', '2')]
            for text in bad:
                sample = benchResult('fixture', 0, text)
                self.assertFalse(check(sample))
                self.assertEqual(sample['rate'], 0)
                failed = summarizeSamples([good, sample])
                self.assertFalse(failed['valid'])
                self.assertEqual(failed['rate'], 0)
                self.assertIsNone(bestResult([failed]))
            env['sh'] = lambda *a, **k: (0, bad[0])
            measure = function('measureBench', env)
            self.assertFalse(measure(1, 1, 0, False, 1, packed=True)['valid'])
            self.assertTrue(measure(1, 1, 0, False, 1, packed=False)['valid'])

    def test_source_digest_covers_generator_and_generated_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in [('Makefile', ''), ('modal_app.py', ''), ('ecc2k130', 'fixture'),
                               ('generated/eccF131.h', 'LEAF = 66'),
                               ('codegen/genpackedproduct.py', 'generator'),
                               ('include/packedgeneratedproduct131.h', 'header')]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            for mode in ('0', '1'):
                env = environment('1', mode)
                env.update(REMOTE=directory, sh=lambda *a, **k: (0, 'fixture'),
                           buildFor=lambda *a, **k: (True, 'built'))
                identity = function('benchmarkIdentity', env)
                self.assertEqual(identity(True)['packedGeneratedProduct'], mode == '1')
                self.assertIsNone(identity(False)['packedGeneratedProduct'])
                self.assertEqual(function('runCompileCheck', env)()['packedGeneratedProduct'], mode == '1')
                for name in ('codegen/genpackedproduct.py', 'include/packedgeneratedproduct131.h'):
                    before = identity(True)['sourceSha256']
                    path = root / name
                    path.write_text(path.read_text() + '\nchanged')
                    self.assertNotEqual(identity(True)['sourceSha256'], before)

    def test_benchmark_and_autotune_metadata_preserve_generated_mode(self):
        for mode in ('0', '1'):
            env = environment('1', mode)
            env.update(buildFor=lambda *a, **k: (True, 'built'),
                       benchmarkIdentity=lambda *a, **k: {},
                       measureBench=lambda *a, **k: dict(valid=True, rate=6000.0),
                       os=SimpleNamespace(makedirs=lambda *a, **k: None),
                       open=lambda *a, **k: io.StringIO(),
                       volume=SimpleNamespace(commit=lambda: None))
            self.assertEqual(function('runBench', env)(rebuild=False, packed=True)['packedGeneratedProduct'], mode == '1')
            function('autotuneConfigs', env)
            tune = function('runAutotune', env)(configs='0:32:128:2', packed=True)
            self.assertEqual(tune['results'][0]['packedGeneratedProduct'], mode == '1')

    def audit_fixture(self, mode, arithmetic=None, failed_phase=None, failed_marker=None,
                      clmad='0', clmad_arithmetic=None, batch=32,
                      weighted='0', weighted_arithmetic=None, paired_sigma=None,
                      tile='0', compact='0', storage_output=None, storage_returncode=0,
                      failed_compact_phase=None, failed_compact_marker=None, build_calls=None,
                      shared='0', shared_probe_output=None, shared_probe_returncode=0,
                      failed_shared_phase=None, failed_shared_marker=None, block_threads=128,
                      square='0', square_arithmetic=None, karat='0', karat_arithmetic=None):
        with tempfile.TemporaryDirectory() as directory:
            commands = []
            env = environment('1', mode, clmad=clmad, weighted=weighted, tile=tile, compact=compact, shared=shared, square=square, karat=karat)
            workers = 6160384 // batch
            def output(weight, phase):
                marker = mode if failed_phase != phase else failed_marker
                compactMarker = compact if failed_compact_phase != phase else failed_compact_marker
                sharedMarker = shared if failed_shared_phase != phase else failed_shared_marker
                text = (f'packed direct reduction: 1\n'
                        f'packed generated product: {marker}\n'
                        f'packed state tile: {tile}\n'
                        f'packed native carryless multiply: {clmad}\n'
                        f'packed native carryless square: {square}\n'
                        f'packed three-limb Karatsuba: {karat}\n'
                        f'packed weighted prefix: {weighted}\n'
                        f'packed compact state: {compactMarker}\n'
                        f'packed shared sigma: {sharedMarker}\n'
                        f'packed top clmad: 0\n'
                        f'backend cuda-packed131: {workers} threads x {batch} slots x 1 lanes = {workers * batch} walks, '
                        f'dp weight {weight}, 1024 steps per launch\n'
                        '1.0 s 6000.000 M it/s 201863462912 iterations 1 dp 1 stored 0 dropped\n'
                        'finished: 6000.000 M it/s, 1 distinguished points (0 verified against the reference, 0 dropped)\n')
                return text.replace('packed generated product: None\n', '').replace('packed compact state: None\n', '').replace('packed shared sigma: None\n', '')
            env['sh'] = lambda *a, **k: (0, output(0, 'benchmark'))
            function('checkPackedReduction', env)
            function('measureBench', env)
            client = SimpleNamespace(**env)
            client.REMOTE = directory
            def build(requested, *args, **kwargs):
                if build_calls is not None:
                    build_calls.append(requested)
                return requested == batch, 'built'
            client.buildFor = build
            client.benchmarkIdentity = lambda **k: {'packedGeneratedProduct': mode == '1'}
            client.volume = SimpleNamespace(commit=lambda: None)
            def run(command, **kwargs):
                commands.append(command)
                if command[:2] == ['make', 'test-packed-storage-cuda']:
                    text = (f'packed storage compact state: {compact}\n'
                            f'packed storage batch: {batch}\n'
                            f'PASS: 128 GPU storage cases, {18584 * batch} records, independent physical images and logical reads with canaries\n')
                    return SimpleNamespace(returncode=storage_returncode,
                                           stdout=text if storage_output is None else storage_output, stderr='')
                elif command[:2] == ['make', 'test-shared-sigma-cuda']:
                    text = (f'packed shared sigma probe: {shared}\n'
                            'PASS: 21 GPU sigma scenarios, 21036 input pairs, global and selected helpers against independent routing\n'
                            'PASS: 114 complete block mask snapshots, 51072 words, output guards and inactive blocks\n')
                    return SimpleNamespace(returncode=shared_probe_returncode,
                                           stdout=text if shared_probe_output is None else shared_probe_output, stderr='')
                elif command[0] == 'make':
                    text = ('packed arithmetic direct reduction: 1\n'
                            + (f'packed arithmetic native carryless square: {square}\n' if square_arithmetic is None else square_arithmetic)
                            + (f'packed arithmetic three-limb Karatsuba: {karat}\n' if karat_arithmetic is None else karat_arithmetic)
                             + (f'packed arithmetic native carryless multiply: {clmad}\n' if clmad_arithmetic is None else clmad_arithmetic)
                            + (f'packed arithmetic weighted prefix: {weighted}\n' if weighted_arithmetic is None else weighted_arithmetic)
                            + ('PASS: 6240 GPU paired Frobenius vectors, both inputs against independent routing\n' if paired_sigma is None else paired_sigma)
                            + (f'packed arithmetic generated product: {mode}\n' if arithmetic is None else arithmetic))
                elif command[0] == 'python3':
                    text = 'integration passed\n'
                else:
                    Path(command[command.index('--dp-file') + 1]).write_bytes(bytes(32))
                    text = output(34, 'collection')
                return SimpleNamespace(returncode=0, stdout=text, stderr='')
            def path(value):
                return Path(directory) / 'artifact' if str(value).startswith('/data/') else Path(value)
            audit_env = dict(client=client, re=re, json=json, time=time, tempfile=tempfile,
                             print=lambda *a, **k: None, subprocess=SimpleNamespace(run=run), Path=path)
            function('checkScalarCounts', audit_env, 'packed_audit.py')
            result = function('runAudit', audit_env, 'packed_audit.py')(repeats=1, workers=workers, batch=batch, blockThreads=block_threads)
            return result, commands

    def test_native_audit_forwards_flag_and_records_expected_and_actual_modes(self):
        for mode in ('0', '1'):
            result, commands = self.audit_fixture(mode)
            self.assertTrue(result['valid'], result.get('error'))
            self.assertIn('PACKED_GENERATED_PRODUCT=' + mode, commands[0])
            for row in [result, result['deviceArithmetic'], *result['benchmark']['samples'], *result['collection']]:
                self.assertEqual(row['expectedPackedGeneratedProduct'], mode == '1')
                self.assertEqual(row['packedGeneratedProduct'], mode == '1')
            self.assertEqual(result['collection'][0]['corpusBytes'], 32)
            self.assertEqual(result['benchmark']['samples'][0]['reportedIterations'], 201863462912)

    def test_native_audit_forwards_nondefault_batch(self):
        for batch in (8, 16):
            result, commands = self.audit_fixture('1', clmad='1', batch=batch)
            self.assertTrue(result['valid'], result.get('error'))
            self.assertEqual(result['batch'], batch)
            self.assertIn('BATCH=' + str(batch), commands[0])
            for sample in [*result['benchmark']['samples'], *result['collection']]:
                self.assertEqual(sample['actualBatch'], batch)
                self.assertEqual(sample['requestedBatch'], batch)
                self.assertEqual(sample['reportedIterations'], 201863462912)

    def test_arithmetic_identity_failure_stops_before_integration_or_timing(self):
        for mode in ('0', '1'):
            for marker in ('', f'packed arithmetic generated product: {1 - int(mode)}\n',
                           f'packed arithmetic generated product: {mode}\n' * 2,
                           'packed arithmetic generated product: 2\n'):
                result, commands = self.audit_fixture(mode, arithmetic=marker)
                self.assertFalse(result['valid'])
                self.assertIn('generated product identity', result['error'])
                self.assertEqual(len(commands), 1)
                self.assertNotIn('integration', result)

    def test_native_benchmark_and_collection_reject_stale_or_missing_markers(self):
        for mode in ('0', '1'):
            for phase in ('benchmark', 'collection'):
                for marker in (str(1 - int(mode)), None):
                    with self.subTest(mode=mode, phase=phase, marker=marker):
                        result, _ = self.audit_fixture(mode, failed_phase=phase, failed_marker=marker)
                        self.assertFalse(result['valid'])
                        row = (result['benchmark']['samples'] if phase == 'benchmark' else result['collection'])[0]
                        self.assertFalse(row['valid'])
                        self.assertEqual(row['rate'], 0)


class StateTileBuildTests(unittest.TestCase):
    def test_environment_and_dependencies(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_STATE_TILE' for t in node.targets))
        for value in (None, '0', '256', '', '1', '128', '0256', 'true'):
            for missing in (None, 'POLY_STATE', 'CACHE_DENOM', 'POLY_CHAIN'):
                values = {} if value is None else {'ECC_PACKED_STATE_TILE': value}
                env = dict(os=SimpleNamespace(environ=values), PACKED_POLY_STATE='1',
                           PACKED_CACHE_DENOM='1', PACKED_POLY_CHAIN='1')
                if missing:
                    env['PACKED_' + missing] = '0'
                valid = value in (None, '0') or (value == '256' and missing is None)
                with self.subTest(value=value, missing=missing):
                    if valid:
                        execute(body[index:index + 3], env)
                        self.assertEqual(env['PACKED_STATE_TILE'], value or '0')
                    else:
                        with self.assertRaises(ValueError):
                            execute(body[index:index + 3], env)

    def test_baked_image_geometry_matches_layout(self):
        class Image:
            def __init__(self):
                self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for tile, threads in (('0', 128), ('256', 256)):
            env = environment('1', '1', tile)
            image = Image()
            env.update(modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)),
                       GENCODE='fixture', LOCAL=ROOT)
            assignment('image', env)
            builds = [s for s in image.calls['run_commands'] if 'make gpu ' in s]
            self.assertEqual(len(builds), 1)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_STATE_TILE'], tile)
            self.assertIn('THREADS=' + str(threads), builds[0])
            self.assertIn('PACKED_STATE_TILE=' + tile, builds[0])
            self.assertEqual(env['BAKED']['threads'], threads)
            self.assertEqual(env['BAKED']['packedStateTile'], int(tile))

    def test_rebuild_cannot_reuse_another_layout(self):
        env = environment('1', '1', '0')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda command, **kwargs: (commands.append(command) or 0, ''))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0, arch='120')[0])
        self.assertEqual(commands, [])
        env['PACKED_STATE_TILE'] = '256'
        self.assertTrue(build(32, 256, 0, arch='120')[0])
        self.assertIn('PACKED_STATE_TILE=256', commands[-1])
        self.assertFalse(env['bakedIntact'][0])

    def test_incompatible_block_size_stops_before_build(self):
        env = environment('1', '1', '256')
        env['sh'] = env['shStream'] = lambda *a, **k: self.fail('invalid layout must not invoke compiler')
        ok, error = function('buildFor', env)(32, 128, 0, arch='120')
        self.assertFalse(ok)
        self.assertIn('256 threads per block', error)

    def test_missing_wrong_and_duplicate_tile_cannot_rank(self):
        for tile in ('0', '256'):
            env = environment('1', '1', tile)
            check = function('checkPackedReduction', env)
            text = raw('1', '1', tile)
            good = benchResult(['fixture'], 0, text)
            self.assertTrue(check(good))
            self.assertEqual(good['packedStateTile'], int(tile))
            for bad in (text.replace(f'packed state tile: {tile}\n', ''),
                        raw('1', '1', '256' if tile == '0' else '0'),
                        text + f'packed state tile: {tile}\n',
                        text + 'packed state tile: true\n',
                        text.replace(f'packed state tile: {tile}', 'packed state tile: 1')):
                sample = benchResult(['fixture'], 0, bad)
                self.assertFalse(check(sample))
                self.assertEqual(sample['rate'], 0)
                self.assertFalse(summarizeSamples([good, sample])['valid'])


class ClmadSquareBuildTests(unittest.TestCase):
    def test_environment_guards(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_CLMAD_SQUARE' for t in node.targets))
        for multiply in ('0', '1'):
            for value in (None, '0', '1', '', '2', '-1', 'true'):
                env = dict(PACKED_CLMAD=multiply, os=SimpleNamespace(
                    environ={} if value is None else {'ECC_PACKED_CLMAD_SQUARE': value}))
                allowed = value in (None, '0') or (value == '1' and multiply == '1')
                with self.subTest(multiply=multiply, square=value):
                    if allowed:
                        execute(body[index:index + 3], env)
                        self.assertEqual(env['PACKED_CLMAD_SQUARE'], value or '0')
                    else:
                        with self.assertRaises(ValueError):
                            execute(body[index:index + 3], env)

    def test_cache_rebuild_and_mode_gate(self):
        env = environment('1', '1', clmad='1')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        env['PACKED_CLMAD_SQUARE'] = '1'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_CLMAD_SQUARE=1', commands[-1])
        check = function('checkPackedReduction', env)
        text = raw('1', '1', clmad='1', square='1')
        marker = 'packed native carryless square: 1\n'
        for bad in (text.replace(marker, ''), text + marker,
                    text.replace(marker, 'packed native carryless square: 0\n'),
                    text.replace(marker, 'packed native carryless square: true\n')):
            sample = benchResult(['fixture'], 0, bad)
            self.assertFalse(check(sample))
            self.assertEqual(sample['rate'], 0)
        self.assertTrue(check(benchResult(['fixture'], 0, text)))

    def test_audit_checks_candidate_arithmetic_before_timing(self):
        fixture = GeneratedProductBuildTests()
        for square in ('0', '1'):
            result, commands = fixture.audit_fixture('1', clmad='1', square=square)
            self.assertTrue(result['valid'], result)
            self.assertIn('PACKED_CLMAD_SQUARE=' + square, commands[0])
            self.assertEqual(result['packedClmadSquare'], square == '1')
            marker = 'packed arithmetic native carryless square: ' + square + '\n'
            for bad in ('', marker * 2, 'packed arithmetic native carryless square: true\n',
                        'packed arithmetic native carryless square: ' + str(1-int(square)) + '\n'):
                result, commands = fixture.audit_fixture('1', clmad='1', square=square, square_arithmetic=bad)
                self.assertFalse(result['valid'])
                self.assertIn('CLMAD square identity', result['error'])
                self.assertEqual(len(commands), 1)


class Karat3BuildTests(unittest.TestCase):
    def test_environment_guards(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_KARAT3' for t in node.targets))
        for multiply in ('0', '1'):
            for value in (None, '0', '1', '', '2', '-1', 'true'):
                env = dict(PACKED_CLMAD=multiply, os=SimpleNamespace(
                    environ={} if value is None else {'ECC_PACKED_KARAT3': value}))
                allowed = value in (None, '0') or (value == '1' and multiply == '1')
                with self.subTest(multiply=multiply, karat=value):
                    if allowed:
                        execute(body[index:index + 3], env)
                        self.assertEqual(env['PACKED_KARAT3'], value or '0')
                    else:
                        with self.assertRaises(ValueError):
                            execute(body[index:index + 3], env)

    def test_cache_rebuild_and_mode_gate(self):
        env = environment('1', '1', clmad='1')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        env['PACKED_KARAT3'] = '1'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_KARAT3=1', commands[-1])
        check = function('checkPackedReduction', env)
        text = raw('1', '1', clmad='1', karat='1')
        marker = 'packed three-limb Karatsuba: 1\n'
        for bad in (text.replace(marker, ''), text + marker,
                    text.replace(marker, 'packed three-limb Karatsuba: 0\n'),
                    text.replace(marker, 'packed three-limb Karatsuba: true\n')):
            sample = benchResult(['fixture'], 0, bad)
            self.assertFalse(check(sample))
            self.assertEqual(sample['rate'], 0)
        self.assertTrue(check(benchResult(['fixture'], 0, text)))

    def test_audit_checks_candidate_arithmetic_before_timing(self):
        fixture = GeneratedProductBuildTests()
        for karat in ('0', '1'):
            result, commands = fixture.audit_fixture('1', clmad='1', karat=karat)
            self.assertTrue(result['valid'], result)
            self.assertIn('PACKED_KARAT3=' + karat, commands[0])
            self.assertEqual(result['packedKarat3'], karat == '1')
            marker = 'packed arithmetic three-limb Karatsuba: ' + karat + '\n'
            for bad in ('', marker * 2, 'packed arithmetic three-limb Karatsuba: true\n',
                        'packed arithmetic three-limb Karatsuba: ' + str(1-int(karat)) + '\n'):
                result, commands = fixture.audit_fixture('1', clmad='1', karat=karat, karat_arithmetic=bad)
                self.assertFalse(result['valid'])
                self.assertIn('Karat3 identity', result['error'])
                self.assertEqual(len(commands), 1)


class ClmadBuildTests(unittest.TestCase):
    def test_environment_defaults_and_rejects_invalid_values(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_CLMAD' for t in node.targets))
        for value in (None, '0', '1', '', '2', '-1', 'true'):
            env = dict(os=SimpleNamespace(environ={} if value is None else {'ECC_PACKED_CLMAD': value}))
            with self.subTest(value=value):
                if value in (None, '0', '1'):
                    execute(body[index:index + 2], env)
                    self.assertEqual(env['PACKED_CLMAD'], value or '0')
                else:
                    with self.assertRaises(ValueError):
                        execute(body[index:index + 2], env)

    def test_image_and_cache_preserve_native_mode(self):
        class Image:
            def __init__(self): self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1'):
            env = environment('1', '1', clmad=mode)
            image = Image()
            env.update(CUDA_VERSION='13.3.1', GENCODE='fixture', LOCAL=ROOT,
                       modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)))
            assignment('image', env)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_CLMAD'], mode)
            builds = [c for c in image.calls['run_commands'] if 'make gpu ' in c]
            self.assertEqual(len(builds), 1)
            self.assertIn('PACKED_CLMAD=' + mode, builds[0])
            self.assertEqual(env['BAKED']['packedClmad'], mode == '1')
        env = environment('1', '1')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        env['PACKED_CLMAD'] = '1'
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            function('runBench', env)(rebuild=False, packed=True)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_CLMAD=1', commands[-1])
        env['PACKED_CLMAD'] = '0'
        self.assertTrue(build(32, 128, 0)[0])
        self.assertIn('PACKED_CLMAD=0', commands[-1])

    def test_missing_wrong_or_duplicate_identity_cannot_rank(self):
        for mode in ('0', '1'):
            check = function('checkPackedReduction', environment('1', '1', clmad=mode))
            text = raw('1', '1', clmad=mode)
            good = benchResult('fixture', 0, text)
            self.assertTrue(check(good))
            self.assertEqual(good['packedClmad'], mode == '1')
            marker = f'packed native carryless multiply: {mode}\n'
            for bad in (text.replace(marker, ''), text + marker,
                        raw('1', '1', clmad=str(1 - int(mode))), raw('1', '1', clmad='2')):
                sample = benchResult('fixture', 0, bad)
                self.assertFalse(check(sample))
                self.assertEqual(sample['rate'], 0)
                self.assertFalse(summarizeSamples([good, sample])['valid'])

    def test_benchmark_and_autotune_record_native_mode(self):
        for mode in ('0', '1'):
            env = environment('1', '1', clmad=mode)
            env.update(buildFor=lambda *a, **k: (True, 'built'),
                       benchmarkIdentity=lambda *a, **k: {},
                       measureBench=lambda *a, **k: dict(valid=True, rate=6000.0),
                       os=SimpleNamespace(makedirs=lambda *a, **k: None),
                       open=lambda *a, **k: io.StringIO(), volume=SimpleNamespace(commit=lambda: None))
            self.assertEqual(function('runBench', env)(rebuild=False, packed=True)['packedClmad'], mode == '1')
            function('autotuneConfigs', env)
            tune = function('runAutotune', env)(configs='0:32:128:2', packed=True)
            self.assertEqual(tune['results'][0]['packedClmad'], mode == '1')

    def test_audit_binds_arithmetic_and_timed_modes(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            result, commands = fixture.audit_fixture('1', clmad=mode)
            self.assertTrue(result['valid'], result.get('error'))
            self.assertIn('PACKED_CLMAD=' + mode, commands[0])
            for row in [result, result['deviceArithmetic'], *result['benchmark']['samples'], *result['collection']]:
                self.assertEqual(row['expectedPackedClmad'], mode == '1')
                self.assertEqual(row['packedClmad'], mode == '1')
            for marker in ('', f'packed arithmetic native carryless multiply: {1 - int(mode)}\n',
                           f'packed arithmetic native carryless multiply: {mode}\n' * 2):
                failed, commands = fixture.audit_fixture('1', clmad=mode, clmad_arithmetic=marker)
                self.assertFalse(failed['valid'])
                self.assertIn('CLMAD identity', failed['error'])
                self.assertEqual(len(commands), 1)
                self.assertNotIn('integration', failed)


class WeightedPrefixBuildTests(unittest.TestCase):
    def weighted_environment_nodes(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_WEIGHTED_PREFIX' for t in node.targets))
        return body[index:index + 4]

    def test_environment_enforces_modes_and_required_parent_options(self):
        body = self.weighted_environment_nodes()
        parents = ('POLY_STATE', 'POLY_CHAIN', 'CACHE_DENOM', 'PAIR_PRODUCTS')
        def env(value, **overrides):
            result = dict(os=SimpleNamespace(environ={} if value is None else {'ECC_PACKED_WEIGHTED_PREFIX': value}),
                          PACKED_PERM_SIGMA='3', **{'PACKED_' + key: '1' for key in parents})
            result.update(overrides)
            return result
        for value in (None, '0', '1', '2', '-1', '3', '', 'true'):
            scope = env(value)
            if value in (None, '0', '1', '2'):
                execute(body, scope)
                self.assertEqual(scope['PACKED_WEIGHTED_PREFIX'], value or '0')
            else:
                with self.assertRaises(ValueError): execute(body, scope)
        for parent in parents:
            for mode in ('1', '2'):
                with self.assertRaises(ValueError):
                    execute(body, env(mode, **{'PACKED_' + parent: '0'}))
            execute(body, env('0', **{'PACKED_' + parent: '0'}))
        for mask in ('0', '2'):
            with self.assertRaises(ValueError): execute(body, env('2', PACKED_PERM_SIGMA=mask))
            execute(body, env('1', PACKED_PERM_SIGMA=mask))

    def test_image_and_rebuild_identity_bind_the_exact_schedule(self):
        class Image:
            def __init__(self): self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1', '2'):
            scope = environment('1', '1', clmad='1', weighted=mode)
            image = Image()
            scope.update(CUDA_VERSION='13.3.1', GENCODE='fixture', LOCAL=ROOT,
                         modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)))
            assignment('image', scope)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_WEIGHTED_PREFIX'], mode)
            builds = [line for line in image.calls['run_commands'] if 'make gpu ' in line]
            self.assertEqual(len(builds), 1)
            self.assertIn('PACKED_WEIGHTED_PREFIX=' + mode, builds[0])
            self.assertEqual(scope['BAKED']['packedWeightedPrefix'], int(mode))
        scope = environment('1', '1', clmad='1')
        commands = []
        scope.update(sh=lambda *a, **k: (0, ''),
                     shStream=lambda command, **k: (commands.append(command) or 0, 'built'))
        build = function('buildFor', scope)
        self.assertTrue(build(32, 128, 0)[0])
        self.assertEqual(commands, [])
        for mode in ('2', '1', '0'):
            scope['PACKED_WEIGHTED_PREFIX'] = mode
            with self.assertRaisesRegex(ValueError, 'matching baked binary'):
                function('runBench', scope)(rebuild=False, packed=True)
            self.assertTrue(build(32, 128, 0)[0])
            self.assertIn('PACKED_WEIGHTED_PREFIX=' + mode, commands[-1])

    def test_missing_wrong_or_duplicate_schedule_cannot_rank(self):
        for mode in ('0', '1', '2'):
            check = function('checkPackedReduction', environment('1', '1', clmad='1', weighted=mode))
            text = raw('1', '1', clmad='1', weighted=mode)
            good = benchResult('fixture', 0, text)
            self.assertTrue(check(good))
            self.assertEqual(good['packedWeightedPrefix'], int(mode))
            marker = f'packed weighted prefix: {mode}\n'
            for bad in (text.replace(marker, ''), text + marker,
                        raw('1', '1', clmad='1', weighted=str((int(mode) + 1) % 3)),
                        raw('1', '1', clmad='1', weighted='3')):
                row = benchResult('fixture', 0, bad)
                self.assertFalse(check(row))
                self.assertEqual(row['rate'], 0)
                self.assertFalse(summarizeSamples([good, row])['valid'])

    def test_audit_requires_schedule_and_paired_device_validation(self):
        fixture = GeneratedProductBuildTests()
        paired = 'PASS: 6240 GPU paired Frobenius vectors, both inputs against independent routing\n'
        for mode in ('0', '1', '2'):
            result, commands = fixture.audit_fixture('1', clmad='1', weighted=mode, batch=16)
            self.assertTrue(result['valid'], result.get('error'))
            self.assertIn('PACKED_WEIGHTED_PREFIX=' + mode, commands[0])
            for row in [result, result['deviceArithmetic'], *result['benchmark']['samples'], *result['collection']]:
                self.assertEqual(row['expectedPackedWeightedPrefix'], int(mode))
                self.assertEqual(row['packedWeightedPrefix'], int(mode))
            for marker in ('', f'packed arithmetic weighted prefix: {(int(mode) + 1) % 3}\n',
                           f'packed arithmetic weighted prefix: {mode}\n' * 2):
                failed, commands = fixture.audit_fixture('1', clmad='1', weighted=mode, weighted_arithmetic=marker)
                self.assertFalse(failed['valid'])
                self.assertIn('weighted prefix identity', failed['error'])
                self.assertEqual(len(commands), 1)
                self.assertNotIn('integration', failed)
            for marker in ('', paired * 2):
                failed, commands = fixture.audit_fixture('1', clmad='1', weighted=mode, paired_sigma=marker)
                self.assertFalse(failed['valid'])
                self.assertIn('paired Frobenius validation', failed['error'])
                self.assertEqual(len(commands), 1)
                self.assertNotIn('integration', failed)


class CompactStateBuildTests(unittest.TestCase):
    def test_environment_requires_a_valid_mode_and_all_layout_parents(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_COMPACT_STATE' for t in node.targets))
        compact_nodes = body[index:index + 3]
        def scope(value, **overrides):
            env = dict(os=SimpleNamespace(environ={} if value is None else {'ECC_PACKED_COMPACT_STATE': value}),
                       PACKED_STATE_TILE='256', PACKED_POLY_STATE='1',
                       PACKED_POLY_CHAIN='1', PACKED_CACHE_DENOM='1')
            env.update(overrides)
            return env
        for mode in (None, '0', '1'):
            env = scope(mode)
            execute(compact_nodes, env)
            self.assertEqual(env['PACKED_COMPACT_STATE'], mode or '0')
        for mode in ('2', '-1', '', 'true'):
            with self.assertRaises(ValueError): execute(compact_nodes, scope(mode))
        for parent in ('STATE_TILE', 'POLY_STATE', 'POLY_CHAIN', 'CACHE_DENOM'):
            with self.assertRaises(ValueError):
                execute(compact_nodes, scope('1', **{'PACKED_' + parent: '0'}))
            execute(compact_nodes, scope('0', **{'PACKED_' + parent: '0'}))

    def test_image_build_cache_and_rebuild_keep_the_selected_layout(self):
        class Image:
            def __init__(self): self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1'):
            env = environment('1', '1', tile='256', clmad='1', weighted='2', compact=mode)
            image = Image()
            env.update(CUDA_VERSION='13.3.1', GENCODE='fixture', LOCAL=ROOT,
                       modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)))
            assignment('image', env)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_COMPACT_STATE'], mode)
            build_lines = [line for line in image.calls['run_commands'] if 'make gpu ' in line]
            self.assertEqual(len(build_lines), 1)
            self.assertIn('PACKED_COMPACT_STATE=' + mode, build_lines[0])
            self.assertEqual(env['BAKED']['packedCompactState'], mode == '1')
        env = environment('1', '1', tile='256', clmad='1', weighted='2')
        commands = []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda command, **k: (commands.append(command) or 0, 'built'))
        build = function('buildFor', env)
        self.assertTrue(build(32, 256, 0)[0])
        self.assertEqual(commands, [])
        measured = []
        env.update(benchmarkIdentity=lambda *a, **k: {},
                   measureBench=lambda *a, **k: (measured.append(a) or dict(valid=True, rate=6000.0)))
        bench = function('runBench', env)
        matching = bench(rebuild=False, packed=True, threads=256)
        self.assertTrue(matching['valid'])
        self.assertFalse(matching['packedCompactState'])
        self.assertEqual(len(measured), 1)
        env['PACKED_COMPACT_STATE'] = '1'
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            bench(rebuild=False, packed=True, threads=256)
        self.assertEqual(len(measured), 1)
        self.assertTrue(build(32, 256, 0)[0])
        self.assertIn('PACKED_COMPACT_STATE=1', commands[-1])
        env['PACKED_COMPACT_STATE'] = '0'
        self.assertTrue(build(32, 256, 0)[0])
        self.assertIn('PACKED_COMPACT_STATE=0', commands[-1])
        self.assertFalse(build(32, 128, 0)[0])

    def test_missing_wrong_or_duplicate_layout_cannot_rank(self):
        for mode in ('0', '1'):
            env = environment('1', '1', tile='256', clmad='1', weighted='2', compact=mode)
            check = function('checkPackedReduction', env)
            text = raw('1', '1', tile='256', clmad='1', weighted='2', compact=mode)
            good = benchResult('fixture', 0, text)
            self.assertTrue(check(good))
            self.assertEqual(good['packedCompactState'], mode == '1')
            marker = f'packed compact state: {mode}\n'
            for bad in (text.replace(marker, ''), text + marker,
                        text.replace(marker, f'packed compact state: {1-int(mode)}\n'),
                        text.replace(marker, 'packed compact state: 2\n')):
                row = benchResult('fixture', 0, bad)
                self.assertFalse(check(row))
                self.assertEqual(row['rate'], 0)
                self.assertFalse(summarizeSamples([good, row])['valid'])

    def test_audit_requires_complete_storage_validation_before_timing(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            for batch in (8, 16, 32):
                result, commands = fixture.audit_fixture('1', clmad='1', weighted='2',
                                                        tile='256', compact=mode, batch=batch)
                self.assertTrue(result['valid'], result.get('error'))
                self.assertEqual(commands[1][:2], ['make', 'test-packed-storage-cuda'])
                self.assertIn('PACKED_COMPACT_STATE=' + mode, commands[1])
                self.assertIn('BATCH=' + str(batch), commands[1])
                self.assertEqual(result['deviceStorage']['cases'], 128)
                self.assertEqual(result['deviceStorage']['records'], 18584 * batch)
                for row in [result, result['deviceStorage'], *result['benchmark']['samples'], *result['collection']]:
                    self.assertEqual(row['expectedPackedCompactState'], mode == '1')
                    self.assertEqual(row['packedCompactState'], mode == '1')
            text = (f'packed storage compact state: {mode}\npacked storage batch: 16\n'
                    'PASS: 128 GPU storage cases, 297344 records, independent physical images and logical reads with canaries\n')
            variants = ['', text.replace(f'compact state: {mode}', f'compact state: {1-int(mode)}'),
                        text + f'packed storage compact state: {1-int(mode)}\n',
                        text.replace('batch: 16', 'batch: 32'),
                        text.replace('128 GPU', '127 GPU'), text.replace('297344 records', '297343 records'),
                        text + text]
            for bad in variants:
                result, commands = fixture.audit_fixture('1', clmad='1', weighted='2', tile='256',
                                                        compact=mode, batch=16, storage_output=bad)
                self.assertFalse(result['valid'])
                self.assertIn('storage identity', result['error'])
                self.assertEqual(len(commands), 2)
                self.assertNotIn('integration', result)
                self.assertNotIn('benchmark', result)
            result, commands = fixture.audit_fixture('1', tile='256', compact=mode, storage_returncode=9)
            self.assertFalse(result['valid'])
            self.assertIn('storage validation failed', result['error'])
            self.assertEqual(len(commands), 2)

    def test_audit_timed_rows_cannot_change_the_layout(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            for phase in ('benchmark', 'collection'):
                for marker in (None, str(1-int(mode))):
                    result, _ = fixture.audit_fixture('1', clmad='1', weighted='2', tile='256',
                                                     compact=mode, batch=16,
                                                     failed_compact_phase=phase, failed_compact_marker=marker)
                    self.assertFalse(result['valid'])
                    self.assertIn('deviceStorage', result)

    def test_tiled_storage_batch_limit_is_checked_before_any_build(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            for batch in (65, 128):
                builds = []
                result, commands = fixture.audit_fixture('1', tile='256', compact=mode,
                                                        batch=batch, build_calls=builds)
                self.assertFalse(result['valid'])
                self.assertIn('batch sizes 1 through 64', result['error'])
                self.assertEqual(builds, [])
                self.assertEqual(commands, [])
                self.assertNotIn('build', result)
                self.assertNotIn('identity', result)
            for batch in (1, 64):
                result, _ = fixture.audit_fixture('1', tile='256', compact=mode, batch=batch)
                self.assertTrue(result['valid'], result.get('error'))
                self.assertEqual(result['deviceStorage']['records'], 18584 * batch)
        builds = []
        result, _ = fixture.audit_fixture('1', tile='0', compact='0', batch=128, build_calls=builds)
        self.assertTrue(result['valid'], result.get('error'))
        self.assertEqual(builds, [128])
        self.assertNotIn('deviceStorage', result)


class SharedSigmaBuildTests(unittest.TestCase):
    def test_environment_defaults_and_enforces_mode_and_network_parents(self):
        body = nodes('modal_app.py')
        index = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PACKED_SHARED_SIGMA' for t in node.targets))
        guards = body[index:index + 3]
        for weighted in ('0', '1', '2'):
            for network in ('0', '1', '2', '3'):
                for mode in (None, '0', '1', '', '2', '-1', 'true'):
                    env = dict(PACKED_WEIGHTED_PREFIX=weighted, PACKED_PERM_SIGMA=network,
                               os=SimpleNamespace(environ={} if mode is None else {'ECC_PACKED_SHARED_SIGMA': mode}))
                    allowed = mode in (None, '0') or (mode == '1' and weighted == '2' and int(network) & 1)
                    with self.subTest(mode=mode, weighted=weighted, network=network):
                        if allowed:
                            execute(guards, env)
                            self.assertEqual(env['PACKED_SHARED_SIGMA'], mode or '0')
                        else:
                            with self.assertRaises(ValueError): execute(guards, env)

    def test_image_and_matching_cache_bind_only_the_shared_mode_change(self):
        class Image:
            def __init__(self): self.calls = {}
            def __getattr__(self, name):
                def record(*args, **kwargs):
                    self.calls[name] = args
                    return self
                return record
        for mode in ('0', '1'):
            env = environment('1', '1', tile='256', clmad='1', weighted='2', compact='1', shared=mode)
            image = Image()
            env.update(GENCODE='fixture', LOCAL=ROOT,
                       modal=SimpleNamespace(Image=SimpleNamespace(from_registry=lambda *a, **k: image)))
            assignment('image', env)
            self.assertEqual(image.calls['env'][0]['ECC_PACKED_SHARED_SIGMA'], mode)
            gpu_builds = [c for c in image.calls['run_commands'] if 'make gpu ' in c]
            self.assertEqual(len(gpu_builds), 1)
            self.assertEqual(gpu_builds[0].split().count('PACKED_SHARED_SIGMA=' + mode), 1)
            self.assertEqual(env['BAKED']['packedSharedSigma'], mode == '1')
        env = environment('1', '1', tile='256', clmad='1', weighted='2', compact='1')
        commands, measured = [], []
        env.update(sh=lambda *a, **k: (0, ''),
                   shStream=lambda c, **k: (commands.append(c) or 0, 'built'),
                   benchmarkIdentity=lambda *a, **k: {},
                   measureBench=lambda *a, **k: (measured.append(a) or dict(valid=True, rate=6000.0)))
        build = function('buildFor', env)
        bench = function('runBench', env)
        self.assertTrue(build(32, 256, 0)[0])
        self.assertEqual(commands, [])
        positive = bench(rebuild=False, packed=True, threads=256)
        self.assertTrue(positive['valid'])
        self.assertFalse(positive['packedSharedSigma'])
        self.assertEqual(len(measured), 1)
        # Keep every geometry/parent field identical: only the shared mode differs.
        env['PACKED_SHARED_SIGMA'] = '1'
        with self.assertRaisesRegex(ValueError, 'matching baked binary'):
            bench(rebuild=False, packed=True, threads=256)
        self.assertEqual(len(measured), 1)
        self.assertTrue(build(32, 256, 0)[0])
        self.assertEqual(commands[-1].split().count('PACKED_SHARED_SIGMA=1'), 1)
        env['PACKED_SHARED_SIGMA'] = '0'
        self.assertTrue(build(32, 256, 0)[0])
        self.assertEqual(commands[-1].split().count('PACKED_SHARED_SIGMA=0'), 1)
        self.assertEqual(len(commands), 2)

    def test_every_packed_rate_requires_one_exact_shared_marker(self):
        for mode in ('0', '1'):
            env = environment('1', '1', tile='256', clmad='1', weighted='2', compact='1', shared=mode)
            check = function('checkPackedReduction', env)
            text = raw('1', '1', tile='256', clmad='1', weighted='2', compact='1', shared=mode)
            marker = f'packed shared sigma: {mode}\n'
            good = benchResult('fixture', 0, text)
            self.assertTrue(check(good))
            self.assertEqual(good['packedSharedSigma'], mode == '1')
            self.assertEqual(good['expectedPackedSharedSigma'], mode == '1')
            for output, rc in [(text.replace(marker, ''), 0), (text + marker, 0),
                               (text.replace(marker, f'packed shared sigma: {1-int(mode)}\n'), 0),
                               (text.replace(marker, 'packed shared sigma: true\n'), 0), (text, 9)]:
                sample = benchResult('fixture', rc, output)
                self.assertFalse(check(sample))
                self.assertEqual(sample['rate'], 0)
                self.assertFalse(summarizeSamples([good, sample])['valid'])
            # Function shared bytes are platform observations, not a generic
            # ranking constant. Device-specific resource audits inspect raw output.
            for size in (1792, 2816, 4096):
                sample = benchResult('fixture', 0, text + f'packed kernel: 80 registers/thread, 0 local bytes/thread, {size} shared bytes/block, single-product multiplier\n')
                self.assertTrue(check(sample))
            env['sh'] = lambda *a, **k: (0, text.replace(marker, ''))
            measure = function('measureBench', env)
            self.assertFalse(measure(1, 1, 0, False, 1, packed=True)['valid'])
            self.assertTrue(measure(1, 1, 0, False, 1, packed=False)['valid'])

    def test_identity_bench_autotune_and_compile_metadata_retain_shared_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, contents in [('Makefile', ''), ('modal_app.py', ''), ('ecc2k130', 'binary'),
                                   ('generated/eccF131.h', 'LEAF = 66')]:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(contents)
            for mode in ('0', '1'):
                env = environment('1', '1', tile='256', clmad='1', weighted='2', compact='1', shared=mode)
                env.update(REMOTE=directory, sh=lambda *a, **k: (0, 'fixture'),
                           buildFor=lambda *a, **k: (True, 'built'))
                identity = function('benchmarkIdentity', env)
                self.assertEqual(identity(True)['packedSharedSigma'], mode == '1')
                self.assertIsNone(identity(False)['packedSharedSigma'])
                self.assertEqual(function('runCompileCheck', env)()['packedSharedSigma'], mode == '1')
                env.update(measureBench=lambda *a, **k: dict(valid=True, rate=6000.0),
                           os=SimpleNamespace(makedirs=lambda *a, **k: None),
                           open=lambda *a, **k: io.StringIO(), volume=SimpleNamespace(commit=lambda: None))
                self.assertEqual(function('runBench', env)(rebuild=False, packed=True, threads=256)['packedSharedSigma'], mode == '1')
                function('autotuneConfigs', env)
                tune = function('runAutotune', env)(configs='0:32:256:2', packed=True)
                self.assertEqual(tune['results'][0]['packedSharedSigma'], mode == '1')
                self.assertEqual(tune['results'][0]['identity']['packedSharedSigma'], mode == '1')

    def test_profile_records_actual_shared_mode_and_rejects_wrong_marker(self):
        for mode in ('0', '1'):
            env = environment('1', '1', tile='256', clmad='1', weighted='2', compact='1', shared=mode)
            marker = f'packed shared sigma: {mode}\n'
            env.update(NCU_BINARY='fixture-ncu', HOUR=3600,
                       sh=lambda *a, **k: (0, 'fixture version'), profilerVersionError=lambda text: None,
                       buildFor=lambda *a, **k: (True, 'built'), benchmarkIdentity=lambda packed: {'packedSharedSigma': mode == '1'},
                       profileResult=lambda rc, text: dict(available=True))
            profile = function('runProfile', env)
            for output in (marker, '', marker * 2, f'packed shared sigma: {1-int(mode)}\n'):
                env['shStream'] = lambda *a, output=output, **k: (0, output)
                result = profile(packed=True, threads=256)
                self.assertEqual(result['expectedPackedSharedSigma'], mode == '1')
                self.assertEqual(result['available'], output == marker)
                if output == marker:
                    self.assertEqual(result['packedSharedSigma'], mode == '1')
                else:
                    self.assertEqual(result['kind'], 'packed_identity_mismatch')
            legacy = profile(packed=False)
            self.assertTrue(legacy['available'])
            self.assertIsNone(legacy['packedSharedSigma'])
            env['profileResult'] = lambda rc, text: dict(available=False, kind='counter_permission_denied')
            self.assertEqual(profile(packed=True, threads=256)['kind'], 'counter_permission_denied')

    def test_audit_forwards_same_flags_to_applicable_probe_and_records_actual_mode(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            for tile in ('0', '256'):
                result, commands = fixture.audit_fixture('1', clmad='1', weighted='2', tile=tile,
                                                        compact='1' if tile == '256' else '0', shared=mode,
                                                        batch=16, block_threads=256)
                self.assertTrue(result['valid'], result.get('error'))
                self.assertTrue(result['sharedSigmaProbeApplicable'])
                index = next(i for i, c in enumerate(commands) if c[:2] == ['make', 'test-shared-sigma-cuda'])
                self.assertEqual(commands[index][2:], commands[0][2:])
                self.assertEqual(commands[index].count('PACKED_SHARED_SIGMA=' + mode), 1)
                self.assertIn('THREADS=256', commands[index])
                self.assertEqual(commands[index + 1][0], 'python3')
                probe = result['deviceSharedSigma']
                self.assertEqual([probe[k] for k in ('scenarios', 'inputPairs', 'blockSnapshots', 'maskWords')],
                                 [21, 21036, 114, 51072])
                for row in [result, probe, *result['benchmark']['samples'], *result['collection']]:
                    self.assertEqual(row['expectedPackedSharedSigma'], mode == '1')
                    self.assertEqual(row['packedSharedSigma'], mode == '1')
        for weighted in ('0', '1'):
            result, commands = fixture.audit_fixture('1', weighted=weighted)
            self.assertTrue(result['valid'], result.get('error'))
            self.assertFalse(result['sharedSigmaProbeApplicable'])
            self.assertNotIn('deviceSharedSigma', result)
            self.assertFalse(any(c[:2] == ['make', 'test-shared-sigma-cuda'] for c in commands))
            self.assertFalse(result['packedSharedSigma'])

    def test_failed_or_malformed_probe_stops_before_integration_and_timing(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            marker = f'packed shared sigma probe: {mode}\n'
            passes = ('PASS: 21 GPU sigma scenarios, 21036 input pairs, global and selected helpers against independent routing\n'
                      'PASS: 114 complete block mask snapshots, 51072 words, output guards and inactive blocks\n')
            text = marker + passes
            malformed = ['', passes, text + marker, text + text,
                         text.replace(marker, f'packed shared sigma probe: {1-int(mode)}\n'),
                         text.replace(marker, 'packed shared sigma probe: true\n'),
                         text.replace('21 GPU', '20 GPU'), text.replace('21036 input', '21035 input'),
                         text.replace('114 complete', '113 complete'), text.replace('51072 words', '51071 words'),
                         marker + passes.splitlines()[0] + '\n', text + 'PASS: unexpected suite\n']
            for output, rc in [(bad, 0) for bad in malformed] + [(text, 9)]:
                with self.subTest(mode=mode, output=output, returncode=rc):
                    result, commands = fixture.audit_fixture('1', clmad='1', weighted='2', tile='256',
                                                            compact='1', shared=mode, batch=16, block_threads=256,
                                                            shared_probe_output=output, shared_probe_returncode=rc)
                    self.assertFalse(result['valid'])
                    self.assertIn('shared sigma', result['error'])
                    self.assertEqual(len(commands), 3)
                    self.assertNotIn('integration', result)
                    self.assertNotIn('benchmark', result)
                    self.assertNotIn('collection', result)

    def test_audit_timed_rows_cannot_change_or_omit_the_probe_mode(self):
        fixture = GeneratedProductBuildTests()
        for mode in ('0', '1'):
            for phase in ('benchmark', 'collection'):
                for marker in (None, str(1-int(mode)), mode + '\npacked shared sigma: ' + mode):
                    result, _ = fixture.audit_fixture('1', clmad='1', weighted='2', tile='256', compact='1',
                                                     shared=mode, batch=16, block_threads=256,
                                                     failed_shared_phase=phase, failed_shared_marker=marker)
                    self.assertFalse(result['valid'])
                    self.assertIn('deviceSharedSigma', result)
                    rows = result['benchmark']['samples'] if phase == 'benchmark' else result['collection']
                    self.assertFalse(rows[0]['valid'])
                    self.assertEqual(rows[0]['rate'], 0)

    def test_rtx_preset_defaults_and_override_keep_the_measured_geometry(self):
        for mode in (None, '0', '1'):
            for target in ('bench-rtx-pro6000', 'audit-rtx-pro6000'):
                command = ['make', '-n', target]
                if mode is not None: command.append('RTX_PRO6000_SHARED_SIGMA=' + mode)
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('ECC_PACKED_SHARED_SIGMA=' + (mode or '1'), result.stdout)
                self.assertIn('ECC_PACKED_WEIGHTED_PREFIX=2', result.stdout)
                self.assertIn('--batch 16', result.stdout)
                self.assertIn('--workers 385024', result.stdout)
                self.assertIn('--min-blocks 2', result.stdout)

    def test_preblackwell_targets_bind_gpu_arch_and_fastest_product(self):
        # Ada receipt selected CLMAD=1; Turing has no clmad. See
        # benchmarks/preblackwell/summary.json. B200 is Blackwell sm_100
        # with automatic workers (B200.md).
        cases = (
            ('bench-g6-modal', 'ECC_GPU=L4', '1'),
            ('bench-g6e-modal', 'ECC_GPU=L40S', '1'),
            ('bench-g4dn-modal', 'ECC_GPU=T4', '0'),
            ('bench-b200-modal', 'ECC_GPU=B200', '1'),
            ('bench-waves-modal', 'ECC_GPU=RTX-PRO-6000', '1'),
            ('bench-modal-gpu', 'ECC_GPU=L40S', '1'),
            ('gpu-g6', 'arch=compute_89,code=sm_89', '1'),
            ('gpu-g6e', 'arch=compute_89,code=sm_89', '1'),
            ('gpu-g4dn', 'arch=compute_75,code=sm_75', '0'),
        )
        for target, needle, clmad in cases:
            result = subprocess.run(['make', '-n', target], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(needle, result.stdout)
            hay = result.stdout.replace('ECC_PACKED_CLMAD=', 'PACKED_CLMAD=')
            self.assertIn('PACKED_CLMAD=' + clmad, hay)
            self.assertIn('--batch 16' if target.startswith('bench-') else 'BATCH=16', result.stdout)
        dry = subprocess.run(
            ['make', '-n', 'bench-modal-gpu', 'SURVEY_GPU=T4', 'SURVEY_CLMAD=0'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('ECC_GPU=T4', dry.stdout)
        self.assertIn('ECC_PACKED_CLMAD=0', dry.stdout)
        self.assertNotIn('--workers', dry.stdout)
        bang = subprocess.run(
            ['make', '-n', 'bench-modal-gpu', 'SURVEY_GPU=H100!'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(bang.returncode, 0, bang.stderr)
        self.assertIn('ECC_GPU=H100!', bang.stdout)
        self.assertNotIn('--workers', bang.stdout)
        waves = subprocess.run(
            ['make', '-n', 'bench-waves-modal', 'WAVES_GPU=L40S'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(waves.returncode, 0, waves.stderr)
        self.assertIn('ECC_GPU=L40S', waves.stdout)
        self.assertIn('modal_app.py::waves', waves.stdout)
        self.assertIn('--wave-list', waves.stdout)
        self.assertNotIn('--workers', waves.stdout)


if __name__ == '__main__':
    unittest.main()

