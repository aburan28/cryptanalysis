import unittest
import subprocess

from boolean_native_runner import native_binary, solve_native
from boolean_m4ri_runner import compute_m4ri_basis, solve_m4ri
from descend import make_instance


class BooleanNativeRunnerTests(unittest.TestCase):
    def test_native_completes_implicit_boolean_field_pairs(self):
        binary, _ = native_binary()
        result = subprocess.run([str(binary)], input="2 1 0 -1\n2 0 3\n",
                                text=True, capture_output=True, timeout=10, check=True)
        self.assertEqual(result.stdout.splitlines()[1:], ["2 0 1", "2 0 2"])

    def test_m4ri_low_degree_fallback_completes_field_pairs(self):
        for degree in (0, 1, 2):
            result = compute_m4ri_basis(2, [[0, 3]], timeout=10,
                                       signature_limit=0, matrix_degree=degree)
            if result["status"] == "unavailable":
                self.skipTest(result["detail"])
            self.assertEqual(result["status"], "gb")
            self.assertEqual(result["basis_terms"], [[0, 1], [0, 2]])
            self.assertTrue(result["groebner_verified"])

    def test_compiled_basis_and_curve_replay(self):
        instance = make_instance(11, 3, 2, seed=1)
        result = solve_native(instance, timeout=30, signature_limit=128)
        self.assertEqual(result["status"], "solved")
        self.assertTrue(result["groebner_verified"])
        self.assertTrue(result["generators_reduce_to_zero"])
        self.assertEqual(result["basis_sha256"],
                         "6f22c45b9d2f381664827968cfe9483b62f7b8fe51fdaeecdc715ab6fffcd5a9")

    def test_compiled_nine_variable_basis(self):
        instance = make_instance(17, 3, 3, seed=1)
        result = solve_native(instance, timeout=30, signature_limit=128)
        self.assertEqual(result["status"], "solved")
        self.assertTrue(result["groebner_verified"])
        self.assertTrue(result["generators_reduce_to_zero"])
        self.assertEqual(result["basis_sha256"],
                         "2ceac3a050e73f8fde3dff351c7c2187eef03b076e257a617a801bd3a2d8ecdf")

    def test_m4ri_twelve_variable_basis_and_curve_replay(self):
        instance = make_instance(31, 3, 4, seed=1)
        result = solve_m4ri(instance, timeout=30, signature_limit=8)
        if result["status"] == "unavailable":
            self.skipTest(result["detail"])
        self.assertEqual(result["status"], "solved")
        self.assertEqual(result["signature_insertions"], 8)
        self.assertGreater(result["f5_rows_admitted"], 0)
        self.assertTrue(result["groebner_verified"])
        self.assertTrue(result["generators_reduce_to_zero"])
        self.assertTrue(result["verified"])
        self.assertIn("compile_recipe_sha256", result["native_build"])
        self.assertEqual(result["basis_sha256"],
                         "39ac4999621e74bf0f9001cb28df21fcb937ba5dd252a9a3b6355c76c0e2f36b")


if __name__ == "__main__":
    unittest.main()
