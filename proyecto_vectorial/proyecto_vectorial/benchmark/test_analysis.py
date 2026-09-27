#!/usr/bin/env python3
"""Pruebas del calculo estadistico y del rechazo de datos incompletos."""
import csv
from pathlib import Path
import tempfile
import unittest
from analyze_results import analyze


class AnalysisTests(unittest.TestCase):
    def run_case(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with (directory / 'samples.csv').open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['n', 'version', 'sample', 'kernel_ms'])
                writer.writerows(rows)
            result = analyze(directory)
            self.assertTrue((directory / 'speedup.png').exists())
            return result

    def test_known_statistics(self):
        row = self.run_case([(8, 'scalar', 1, 2), (8, 'scalar', 2, 4),
                             (8, 'vector', 1, 1), (8, 'vector', 2, 2)])[0]
        self.assertEqual(row[:3], [8, 2, 3])
        self.assertAlmostEqual(row[3], 2 ** .5)
        self.assertEqual(row[4], 1.5)
        self.assertAlmostEqual(row[5], .5 ** .5)
        self.assertEqual(row[-1], 2)

    def test_missing_pair(self):
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1), (8, 'scalar', 2, 2)])

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1), (8, 'scalar', 1, 2)])

    def test_nonfinite(self):
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 'nan')])


if __name__ == '__main__':
    unittest.main()
