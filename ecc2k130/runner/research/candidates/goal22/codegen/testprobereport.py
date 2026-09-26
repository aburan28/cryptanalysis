import ast
from pathlib import Path
import os
import signal
import subprocess
import sys
import unittest

from profilereport import profileResult


def loadFunction(name, env):
    path = Path(__file__).resolve().parents[1] / 'profile_diagnostic.py'
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), env)
    return env[name]


class ProbeTests(unittest.TestCase):
    def testCommandSuccessAndTimeout(self):
        run = loadFunction('runCommand', dict(os=os, signal=signal, subprocess=subprocess))
        good = run([sys.executable, '-c', 'print("control complete")'])
        self.assertEqual(good['returncode'], 0)
        self.assertFalse(good['timedOut'])
        self.assertIn('control complete', good['output'])
        slow = run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.05)
        self.assertTrue(slow['timedOut'])
        self.assertIsNotNone(slow['returncode'])

    def testTimeoutCannotBecomeSuccess(self):
        classify = loadFunction('classifyProbe', dict(profileResult=profileResult))
        result = classify(dict(returncode=0, timedOut=True,
                               output='==PROF== Profiling "probeKernel": 100%\n'))
        self.assertFalse(result['available'])
        self.assertEqual(result['kind'], 'timeout')

    def testGenericFailureRemainsUnclassified(self):
        classify = loadFunction('classifyProbe', dict(profileResult=profileResult))
        result = classify(dict(returncode=9, timedOut=False,
                               output='==ERROR== Failed to prepare kernel for profiling\n'))
        self.assertFalse(result['available'])
        self.assertEqual(result['kind'], 'profiling_failed')


if __name__ == '__main__':
    unittest.main()
