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
        self.assertFalse(verify.close(float('inf'), float('inf'), 1e-4, 1e-6))

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
