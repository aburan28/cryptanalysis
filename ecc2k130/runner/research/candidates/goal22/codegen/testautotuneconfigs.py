"""The shortlist autolab emits has to mean in modal_app what it meant in autolab.

The two are joined by a string of colon-separated integers and nothing else, so
a change to the number of fields is a change to a wire format that no compiler
checks.  Adding the three knobs made a four-field entry ambiguous -- it could
have meant "knobs off" or "knobs as the run-level flags say" -- and picking the
second silently would have made every shortlist emitted before the knobs existed
mean something different from what it meant when it was written.  These pin the
choice, and pin that a malformed entry is an error rather than a truncation.
"""

import ast
from pathlib import Path
import unittest


def loadFunction(name, env):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'modal_app.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'modal_app.py', 'exec'), env)
    return env[name]


autotuneConfigs = loadFunction('autotuneConfigs', {})


class ConfigParsingTests(unittest.TestCase):
    def testCrossProductWhenNoConfigsGiven(self):
        got = autotuneConfigs("16,32", "128", "0", "2", "")
        self.assertEqual(got, [(0, 16, 128, 2, False, False, False),
                               (0, 32, 128, 2, False, False, False)])

    def testCrossProductCarriesRunLevelKnobs(self):
        got = autotuneConfigs("32", "128", "0", "2", "", (True, False, True))
        self.assertEqual(got, [(0, 32, 128, 2, True, False, True)])

    def testSevenFieldEntryCarriesItsOwnKnobs(self):
        got = autotuneConfigs("", "", "", "", "0:32:128:2:1:0:0,33:64:128:2:0:0:1")
        self.assertEqual(got, [(0, 32, 128, 2, True, False, False),
                               (33, 64, 128, 2, False, False, True)])

    def testPerEntryKnobsBeatRunLevelFlags(self):
        # A shortlist that holds a streamKarat build beside a plain one is the
        # reason the knobs are per entry at all; a run-level flag must not
        # overwrite what the entry says.
        got = autotuneConfigs("", "", "", "", "0:32:128:2:0:0:0", (True, True, True))
        self.assertEqual(got, [(0, 32, 128, 2, False, False, False)])

    def testFourFieldEntryStillParsesAndTakesRunLevelKnobs(self):
        plain = autotuneConfigs("", "", "", "", "0:32:128:2")
        self.assertEqual(plain, [(0, 32, 128, 2, False, False, False)])
        withFlags = autotuneConfigs("", "", "", "", "0:32:128:2", (False, True, False))
        self.assertEqual(withFlags, [(0, 32, 128, 2, False, True, False)])

    def testMalformedEntryRaisesRatherThanTruncating(self):
        for bad in ("0:32:128", "0:32:128:2:1", "0:32:128:2:1:0:0:1"):
            with self.assertRaises(ValueError, msg=bad):
                autotuneConfigs("", "", "", "", bad)

    def testBlankEntriesAreSkipped(self):
        got = autotuneConfigs("", "", "", "", "0:32:128:2, ,33:32:128:2")
        self.assertEqual(len(got), 2)


if __name__ == '__main__':
    unittest.main()
