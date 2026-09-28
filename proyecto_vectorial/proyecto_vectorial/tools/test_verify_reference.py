#!/usr/bin/env python3
"""Comprueba que el verificador detecta resultados incorrectos y archivos invalidos."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
import verify_reference as verify


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.values = np.arange(1, 16, dtype=np.float32)
        self.stats, self.output = verify.reference_stats(self.values)

    def check(self, stats, output):
        with contextlib.redirect_stdout(io.StringIO()):
            return verify.compare(self.values, {'Scalar': (self.stats, self.output),
                                               'AVX2': (stats, output)}, 1e-4, 1e-6)

    def test_correct_results(self):
        self.assertTrue(self.check(self.stats, self.output))

    def test_each_statistic(self):
        for key in verify.FIELDS:
            with self.subTest(key=key):
                bad = dict(self.stats)
                bad[key] = float(bad[key]) + 100
                self.assertFalse(self.check(bad, self.output))

    def test_missing_tail(self):
        bad = self.output.copy()
        bad[8:] = 0
        self.assertFalse(self.check(self.stats, bad))

    def test_nan(self):
        bad = self.output.copy()
        bad[-1] = np.nan
        self.assertFalse(self.check(self.stats, bad))

    def test_constant_contract(self):
        values = np.full(16, 5, dtype=np.float32)
        stats, output = verify.reference_stats(values)
        self.assertEqual(stats['stddev'], 0)
        np.testing.assert_array_equal(values, output)

    def test_binary_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.dat'
            for raw in (b'', struct.pack('<i', -1), struct.pack('<i', 1),
                        struct.pack('<i2f', 1, 2, 3), struct.pack('<if', 1, float('nan'))):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError):
                        verify.read_input(path)

    def test_summary_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'summary.txt'
            for text in ('n=15\n', 'n=15\nn=15\n',
                         'n=15\n' + ''.join(f'{key}=nan\n' for key in verify.FIELDS)):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    verify.read_summary(path)

    def test_tolerance(self):
        self.assertFalse(verify.close(1e-8, 1e-10, 1e-4, 1e-6))
        self.assertTrue(verify.close(1e-7, 0, 1e-4, 1e-6))
        self.assertFalse(verify.close(2e-6, 0, 1e-4, 1e-6))
        self.assertFalse(verify.close(float('inf'), float('inf'), 1e-4, 1e-6))

    def test_nonzero_references_near_zero(self):
        for expected in (1e-10, -1e-10, 1e-30, -1e-30):
            with self.subTest(expected=expected):
                self.assertTrue(verify.close(expected * (1 + 5e-5), expected, 1e-4, 1e-6))
                self.assertFalse(verify.close(expected * (1 + 2e-4), expected, 1e-4, 1e-6))
                self.assertFalse(verify.close(0, expected, 1e-4, 1e-6))

    def test_zero_and_tolerance_boundaries(self):
        for expected in (0.0, -0.0):
            for actual in (0.0, -1e-6, 1e-6):
                self.assertTrue(verify.close(actual, expected, 1e-4, 1e-6))
            self.assertFalse(verify.close(np.nextafter(1e-6, np.inf), expected, 1e-4, 1e-6))
        # Valores binarios exactos para comprobar el limite inclusivo.
        self.assertTrue(verify.close(1.125, 1.0, 0.125, 0))
        self.assertFalse(verify.close(np.nextafter(1.125, np.inf), 1.0, 0.125, 0))
        self.assertTrue(verify.close(1e-10, 1e-10, 0, 0))
        self.assertFalse(verify.close(2e-10, 1e-10, 0, 0))

    def test_discrepancy_mask_matches_acceptance(self):
        expected = np.array([0, 1e-10, -1e-10, 1, 1, 1], dtype=np.float64)
        actual = np.array([1e-7, 1e-8, -1e-8, 1.00001, np.nan, np.inf])
        mask = verify.discrepancy_mask(actual, expected, 1e-4, 1e-6)
        np.testing.assert_array_equal(mask, [False, True, True, False, True, True])
        for a, e, bad in zip(actual, expected, mask):
            self.assertEqual(verify.close(a, e, 1e-4, 1e-6), not bad)
        self.assertFalse(verify.close(actual, expected, 1e-4, 1e-6))
        self.assertFalse(verify.close([1], [1, 2], 1e-4, 1e-6))

    def test_small_statistic_is_rejected(self):
        values = np.array([1e-10], dtype=np.float32)
        stats, output = verify.reference_stats(values)
        bad = dict(stats, sum=1e-8)
        with contextlib.redirect_stdout(io.StringIO()) as log:
            passed = verify.compare(values, {'Scalar': (bad, output)}, 1e-4, 1e-6)
        self.assertFalse(passed)
        self.assertIn('[FAIL] sum_array', log.getvalue())

    def test_small_normalized_value_is_reported(self):
        values = np.array([-1, 1e-10, 1], dtype=np.float32)
        stats, output = verify.reference_stats(values)
        wrong = output.copy()
        wrong[1] = 1e-8
        with contextlib.redirect_stdout(io.StringIO()) as log:
            passed = verify.compare(values, {'Scalar': (stats, wrong)}, 1e-4, 1e-6)
        self.assertFalse(passed)
        self.assertIn('[FAIL] normalizacion: Scalar', log.getvalue())
        self.assertIn('indice=1', log.getvalue())
        self.assertIn('discrepancias=1', log.getvalue())

    def test_formula_uses_own_parameters(self):
        stats = dict(self.stats, mean=np.float32(2.5), stddev=np.float32(3))
        output = (self.values - stats['mean']) / stats['stddev']
        self.assertTrue(verify.normalization_check(self.values, stats, output))
        output[-1] += np.float32(0.01)
        self.assertFalse(verify.normalization_check(self.values, stats, output))

    def test_formula_constant_and_invalid_sigma(self):
        self.assertTrue(verify.normalization_check(self.values, dict(mean=0, stddev=0), self.values.copy()))
        self.assertFalse(verify.normalization_check(self.values, dict(mean=0, stddev=-1), -self.values))

    def test_diagnostic_does_not_hide_failure(self):
        wrong = self.output.copy()
        wrong[0] += 1
        with contextlib.redirect_stdout(io.StringIO()) as log:
            passed = verify.compare(self.values, {'Scalar': (self.stats, wrong)}, 1e-4, 1e-6, True)
        self.assertFalse(passed)
        self.assertIn('math.fsum', log.getvalue())


if __name__ == '__main__':
    unittest.main()
