"""No network or billed resources: constructor and post-creation tag APIs."""
from types import SimpleNamespace
import unittest
from modal_run import create_tagged_sandbox, detach_sandbox


class SandboxCompatTests(unittest.TestCase):
    def test_optional_detach_api(self):
        calls = []
        detach_sandbox(SimpleNamespace(detach=lambda: calls.append('detached')))
        detach_sandbox(SimpleNamespace())
        self.assertEqual(calls, ['detached'])

    def test_constructor_tag_api(self):
        calls = []
        class Sandbox:
            @staticmethod
            def create(*args, tags, **kwargs):
                calls.append((args, tags, kwargs))
                return 'created'
        result = create_tagged_sandbox(SimpleNamespace(Sandbox=Sandbox), 'bash',
                                      tags={'job': 'one'}, timeout=10)
        self.assertEqual(result, 'created')
        self.assertEqual(calls, [(('bash',), {'job': 'one'}, {'timeout': 10})])

    def test_post_creation_tags_and_failed_tag_cleanup(self):
        for fail in (False, True):
            class Sandbox:
                terminated = False
                @classmethod
                def create(cls, *args, timeout):
                    self.assertEqual(args, ('bash',))
                    self.assertEqual(timeout, 10)
                    return cls()
                def set_tags(self, tags):
                    if fail: raise ValueError('metadata failure')
                    self.tags = tags
                def terminate(self):
                    type(self).terminated = True
            module = SimpleNamespace(Sandbox=Sandbox)
            if fail:
                with self.assertRaisesRegex(ValueError, 'metadata failure'):
                    create_tagged_sandbox(module, 'bash', tags={'job': 'one'}, timeout=10)
                self.assertTrue(Sandbox.terminated)
            else:
                result = create_tagged_sandbox(module, 'bash', tags={'job': 'one'}, timeout=10)
                self.assertEqual(result.tags, {'job': 'one'})
                self.assertFalse(Sandbox.terminated)

    def test_unsupported_sdk_fails_before_allocation(self):
        class Sandbox:
            @staticmethod
            def create(*args, **kwargs):
                raise AssertionError('must not allocate')
        with self.assertRaisesRegex(RuntimeError, 'neither constructor tags'):
            create_tagged_sandbox(SimpleNamespace(Sandbox=Sandbox), 'bash', tags={})


if __name__ == '__main__':
    unittest.main()
