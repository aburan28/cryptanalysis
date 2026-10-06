import unittest

from benchreport import benchResult, bestResult, parseRate, reportsVerified, summarizeSamples


def finished(rate='857.163', points=0, verified=0, dropped=0):
    return ('  finished: %s M it/s, %d distinguished points '
            '(%d verified against the reference, %d dropped)\n'
            % (rate, points, verified, dropped))


class BenchmarkTests(unittest.TestCase):
    def testOnlySuccessfulCompletedRunsRank(self):
        progress = '  2.0 s  999.000 M it/s  100 iterations\n'
        for rc, out in [(1, finished()), (0, progress), (0, ''),
                        (0, 'stopping: interrupted\n' + finished()),
                        (0, 'MISMATCH\n' + finished()), (0, finished() * 2)]:
            with self.subTest(rc=rc, out=out):
                result = benchResult('test command', rc, out)
                self.assertFalse(result['valid'])
                self.assertEqual(result['rate'], 0)
                self.assertIsNone(bestResult([result]))
        self.assertEqual(parseRate(progress + finished()), 857.163)

    def testInvalidRates(self):
        for rate in ('nan', 'inf', '-inf', '0', '-3', 'broken'):
            self.assertEqual(parseRate(finished(rate)), 0)

    def testMedianAndFailureAreNotBestProgress(self):
        samples = [benchResult('test command', 0, finished(str(r))) for r in (800, 990, 810)]
        summary = summarizeSamples(samples)
        self.assertEqual((summary['rate'], summary['minRate'], summary['maxRate']), (810, 800, 990))
        self.assertEqual(bestResult([summary]), summary)
        samples.append(benchResult('test command', 2, finished('2000')))
        self.assertFalse(summarizeSamples(samples)['valid'])
        self.assertIsNone(bestResult([summarizeSamples(samples)]))

    def testReportReplayRequiresEvidence(self):
        self.assertTrue(reportsVerified(0, finished(points=100, verified=16)))
        for rc, out in [(2, finished(points=100, verified=16)),
                        (0, finished(points=0, verified=0)),
                        (0, finished(points=100, verified=15)),
                        (0, finished(points=100, verified=16, dropped=1)),
                        (0, 'MISMATCH\n' + finished(points=100, verified=16)),
                        (0, 'progress only')]:
            self.assertFalse(reportsVerified(rc, out))


if __name__ == '__main__':
    unittest.main()
