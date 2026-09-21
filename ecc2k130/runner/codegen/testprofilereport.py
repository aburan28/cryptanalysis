import ast
import contextlib
import io
from pathlib import Path
import unittest
from types import SimpleNamespace

from profilereport import NCU_BINARY, profilerVersionError, profileResult


def loadFunction(name, env):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'modal_app.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'modal_app.py', 'exec'), env)
    return env[name]


class ProfilerTests(unittest.TestCase):
    def testVersionGuard(self):
        self.assertIsNotNone(profilerVersionError('Version 2022.4.1.0 (build 31874700)'))
        self.assertIsNotNone(profilerVersionError('unknown version'))
        self.assertIsNone(profilerVersionError('NVIDIA Nsight Compute\nVersion 2025.3.1.0'))
        self.assertIsNone(profilerVersionError('Version 2026.1.0.0'))

    def testActualFailureIsNotPermissionDenial(self):
        log = ('==ERROR== Failed to prepare kernel for profiling\n'
               '==ERROR== Unknown Error on device 0.\n'
               '==ERROR== Failed to profile "eccWalkKernel" in process 62\n'
               '==ERROR== The application returned an error code (9).\n')
        result = profileResult(9, log)
        self.assertFalse(result['available'])
        self.assertEqual(result['kind'], 'profiling_failed')
        self.assertIn('Failed to prepare kernel', result['why'])
        self.assertEqual(result['log'], log)

    def testErrorsAndEmptyProfilesFailEvenWithZeroExit(self):
        for rc, log in [(0, '==ERROR== Unknown Error'), (1, 'crashed'),
                        (0, '==WARNING== No kernels were profiled'), (0, '')]:
            result = profileResult(rc, log)
            self.assertFalse(result['available'])
            self.assertTrue(result['why'])

    def testExplicitDenialAndSuccess(self):
        denied = profileResult(1, '==ERROR== ERR_NVGPU_DEBUG_PERF_COUNTER_ACCESS_DENIED')
        self.assertEqual(denied['kind'], 'counter_access_denied')
        success = profileResult(0, '==PROF== Profiling "eccWalkKernel": 0%....100% - 5 passes\n')
        self.assertTrue(success['available'])

    def testOldProfilerRejectedBeforeBuildOrLaunch(self):
        env = dict(NCU_BINARY=NCU_BINARY, gpuName=lambda: 'RTX PRO 6000',
                   computeCapability=lambda: '120',
                   sh=lambda cmd: (0, 'Version 2022.4.1.0'),
                   profilerVersionError=profilerVersionError)
        # buildFor and shStream deliberately absent: this must stop first.
        with contextlib.redirect_stdout(io.StringIO()):
            result = loadFunction('runProfile', env)()
        self.assertEqual(result['kind'], 'unsupported_profiler')

    def testCliReturnsFailureAndPrintsReason(self):
        result = profileResult(9, '==ERROR== Failed to prepare kernel for profiling\n')
        env = dict(runProfile=object(),
                   onGpu=lambda fn, gpu: SimpleNamespace(remote=lambda **kw: result))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            loadFunction('profile', env)()
        self.assertEqual(raised.exception.code, 1)
        self.assertIn('Failed to prepare kernel', output.getvalue())
        self.assertNotIn('did not run: None', output.getvalue())

    def testRunProfilePreservesGenericFailure(self):
        calls = []
        log = '==ERROR== Failed to prepare kernel for profiling\n'
        def invoke(command, **kwargs):
            calls.append(command)
            return 9, log
        env = dict(NCU_BINARY=NCU_BINARY, gpuName=lambda: 'RTX PRO 6000',
                   computeCapability=lambda: '120', HOUR=3600,
                   sh=lambda cmd: (0, 'Version 2025.3.1.0'),
                   profilerVersionError=profilerVersionError, profileResult=profileResult,
                   buildFor=lambda *args, **kwargs: (True, ''),
                   benchmarkIdentity=lambda *args, **kwargs: {}, shStream=invoke)
        with contextlib.redirect_stdout(io.StringIO()):
            result = loadFunction('runProfile', env)(workers=128, preferL1=True)
        self.assertEqual(result['kind'], 'profiling_failed')
        self.assertEqual(result['log'], log)
        self.assertEqual(result['command'], calls[0])
        self.assertTrue(calls[0].startswith(NCU_BINARY + ' '))
        self.assertIn('--threads 128 --prefer-l1', calls[0])


if __name__ == '__main__':
    unittest.main()
