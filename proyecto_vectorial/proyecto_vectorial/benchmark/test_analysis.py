#!/usr/bin/env python3
"""Pruebas del calculo estadistico y del rechazo de datos incompletos."""
import builtins
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from analyze_results import analyze


# Usa muestras conocidas para validar el analizador; no mide kernels ni hardware.
class AnalysisTests(unittest.TestCase):
    def run_case(self, rows, cycles=False, inspect=None):
        # Cada caso recibe un CSV temporal aislado. cycles selecciona si
        # incluye la columna TSC; inspect permite comprobar los archivos finales.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with (directory / 'samples.csv').open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['n', 'version', 'sample', 'kernel_ms'] + (['kernel_cycles'] if cycles else []))
                writer.writerows(rows)
            result = analyze(directory)
            # Con matplotlib se genera PNG; sin el, SVG. Siempre debe existir un grafico.
            # Esta comprobacion exige existencia, no una inspeccion visual de su contenido.
            self.assertTrue((directory / 'speedup.png').exists() or (directory / 'speedup.svg').exists())
            if inspect:
                inspect(directory)
            return result

    def test_known_statistics(self):
        # Escalar [2,4]: media 3, desviacion muestral sqrt(2).
        # Vector [1,2]: media 1.5, desviacion muestral sqrt(0.5).
        # Aprobar exige N=8, dos muestras y speedup de medias 3/1.5=2.
        row = self.run_case([(8, 'scalar', 1, 2), (8, 'scalar', 2, 4),
                             (8, 'vector', 1, 1), (8, 'vector', 2, 2)])[0]
        self.assertEqual(row[:3], [8, 2, 3])
        self.assertAlmostEqual(row[3], 2 ** .5)
        self.assertEqual(row[4], 1.5)
        self.assertAlmostEqual(row[5], .5 ** .5)
        self.assertEqual(row[-1], 2)

    def test_cycles_columns(self):
        # Agrega TSC a tiempos conocidos para comprobar ambos resumenes
        # por separado: speedup temporal 2 y cociente de medias TSC 3.
        rows = [(8, 'scalar', 1, 2, 4000), (8, 'scalar', 2, 4, 8000),
                (8, 'vector', 1, 1, 1000), (8, 'vector', 2, 2, 3000)]

        def check(directory):
            # Aprobar exige medias TSC 6000/2000, desviacion escalar
            # 2000*sqrt(2) y preservar las columnas de tiempos del CSV.
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
        # TSC cero debe rechazarse con ValueError. La entrada tambien tiene
        # una sola muestra: esta prueba no distingue que validacion causo el error.
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1, 0)], cycles=True)

    def test_plot_falls_back_to_svg_without_matplotlib(self):
        # Simula falta de matplotlib para comprobar la alternativa SVG,
        # aunque matplotlib este instalado en el entorno de pruebas.
        real_import = builtins.__import__

        def no_matplotlib(name, *args, **kwargs):
            if name.startswith('matplotlib'):
                raise ImportError('simulado')
            return real_import(name, *args, **kwargs)

        rows = [(n, v, i, t) for n, (ts, tv) in ((1000, (6, 1)), (100000, (60, 9)))
                for i in (1, 2) for v, t in (('scalar', ts + i), ('vector', tv + i / 10))]

        def check(directory):
            # Aprobar exige ausencia de PNG y un SVG con curva y texto 8x.
            # Comprueba elementos del archivo, no el aspecto visual completo.
            self.assertFalse((directory / 'speedup.png').exists())
            svg = (directory / 'speedup.svg').read_text(encoding='utf-8')
            self.assertIn('<polyline', svg)
            self.assertIn('8x', svg)  # linea de referencia de 8x

        with patch.object(builtins, '__import__', no_matplotlib):
            self.run_case(rows, inspect=check)

    def test_single_size_svg(self):
        # Un unico N debe poder representarse sin division por cero en el
        # eje logaritmico. Aprobar exige generar el SVG y la etiqueta 6.10x.
        from analyze_results import write_svg
        with tempfile.TemporaryDirectory() as tmp:
            write_svg(Path(tmp) / 'one.svg', [1000], [6.1])  # un solo N no debe fallar
            self.assertIn('6.10x', (Path(tmp) / 'one.svg').read_text(encoding='utf-8'))

    def test_missing_pair(self):
        # Hay dos muestras escalares y ninguna vectorial. Debe rechazarse
        # con ValueError, sin calcular un speedup con una version ausente.
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1), (8, 'scalar', 2, 2)])

    def test_duplicate(self):
        # Repite el indice 1 para la misma version y N. Aprobar exige
        # ValueError; no debe sobrescribir ni contar dos veces esa muestra.
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 1), (8, 'scalar', 1, 2)])

    def test_nonfinite(self):
        # Tiempo NaN debe rechazarse. La entrada tambien es incompleta:
        # la asercion verifica ValueError, no identifica su causa exacta.
        with self.assertRaises(ValueError):
            self.run_case([(8, 'scalar', 1, 'nan')])


if __name__ == '__main__':
    # unittest aprueba solo si todas las aserciones y excepciones esperadas
    # se cumplen; un fallo genera estado de salida distinto de cero.
    unittest.main()
