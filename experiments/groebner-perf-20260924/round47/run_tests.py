"""Retain all adversarial proof tests under every explicit transform mode."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_symmetry
import test_sparse_guard
import test_adapter_isolation
import test_transforms
from transform_accounting import QUERY_MODES


def main():
    reports = []
    cls = test_symmetry.candidate.Checker
    for mode in QUERY_MODES:
        def configured(*args, **kwargs):
            kwargs.setdefault('transform',mode)
            return cls(*args,**kwargs)
        with patch.object(test_symmetry.candidate,'Checker',configured):
            suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                for m in (test_symmetry,test_sparse_guard,test_adapter_isolation))
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        reports.append({'mode':mode,'tests':result.testsRun,'errors':len(result.errors),
                        'failures':len(result.failures),'skipped':len(result.skipped)})
        if not result.wasSuccessful():raise SystemExit(1)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_transforms))
    if not result.wasSuccessful():raise SystemExit(1)
    reports.append({'mode':'integrated-coefficient-audit','tests':result.testsRun,
                    'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped)})
    out=Path(__file__).resolve().parent/'build/unit-results.json'
    out.write_text(json.dumps({'status':'PASS','groups':reports,'timing_eligible':False},indent=2)+'\n')
    print('TRANSFORM_UNIT_PASS',sum(r['tests'] for r in reports),'groups',flush=True)


if __name__=='__main__':main()
