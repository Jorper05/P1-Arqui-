#!/usr/bin/env python3
"""Pruebas del calculo estadistico y del rechazo de datos incompletos."""
import builtins
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analyze_results import analyze


class AnalysisTests(unittest.TestCase):
    def run_case(self, rows, cycles=False, inspect=None):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with (directory / 'samples.csv').open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['n', 'version', 'sample', 'kernel_ms'] + (['kernel_cycles'] if cycles else []))
                writer.writerows(rows)
            result = analyze(directory)
            # Con matplotlib se genera PNG; sin el, SVG. Siempre debe existir un grafico.
            self.assertTrue((directory / 'speedup.png').exists() or (directory / 'speedup.svg').exists())
            if inspect:
                inspect(directory)
            return result

    def test_known_statistics(self):
        row = self.run_case([(8, 'scalar', 1, 2), (8, 'scalar', 2, 4),
                             (8, 'vector', 1, 1), (8, 'vector', 2, 2)])[0]
        self.assertEqual(row[:3], [8, 2, 3])
        self.assertAlmostEqual(row[3], 2 ** .5)
        self.assertEqual(row[4], 1.5)
        self.assertAlmostEqual(row[5], .5 ** .5)
        self.assertEqual(row[-1], 2)

    def test_cycles_columns(self):
        rows = [(8, 'scalar', 1, 2, 4000), (8, 'scalar', 2, 4, 8000),
                (8, 'vector', 1, 1, 1000), (8, 'vector', 2, 2, 3000)]

        def check(directory):
            with (directory / 'summary.csv').open(newline='') as stream:
                summary = next(csv.DictReader(stream))
            self.assertEqual(float(summary['scalar_mean_cycles']), 6000)
            self.assertAlmostEqual(float(summary['scalar_std_cycles']), 2000 * 2 ** .5)
            self.assertEqual(float(summary['vector_mean_cycles']), 2000)
            self.assertEqual(float(summary['speedup_cycles']), 3)
            self.assertEqual(float(summary['speedup']), 2)  # las columnas de ms no cambian

        row = self.run_case(rows, cycles=True, inspect=check)[0]
        self.assertEqual(row[-1], 2)  # analyze() sigue devolviendo el speedup en ms al final

    def test_invalid_cycles(self):
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1, 0)], cycles=True)

    def test_plot_falls_back_to_svg_without_matplotlib(self):
        real_import = builtins.__import__

        def no_matplotlib(name, *args, **kwargs):
            if name.startswith('matplotlib'):
                raise ImportError('simulado')
            return real_import(name, *args, **kwargs)

        rows = [(n, v, i, t) for n, (ts, tv) in ((1000, (6, 1)), (100000, (60, 9)))
                for i in (1, 2) for v, t in (('scalar', ts + i), ('vector', tv + i / 10))]

        def check(directory):
            self.assertFalse((directory / 'speedup.png').exists())
            svg = (directory / 'speedup.svg').read_text(encoding='utf-8')
            self.assertIn('<polyline', svg)
            self.assertIn('8x', svg)  # linea del limite teorico AVX2

        with patch.object(builtins, '__import__', no_matplotlib):
            self.run_case(rows, inspect=check)

    def test_single_size_svg(self):
        from analyze_results import write_svg
        with tempfile.TemporaryDirectory() as tmp:
            write_svg(Path(tmp) / 'one.svg', [1000], [6.1])  # un solo N no debe fallar
            self.assertIn('6.10x', (Path(tmp) / 'one.svg').read_text(encoding='utf-8'))

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
