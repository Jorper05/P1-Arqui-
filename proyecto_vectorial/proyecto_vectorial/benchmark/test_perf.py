#!/usr/bin/env python3
"""Pruebas con contadores sinteticos; no son mediciones de hardware."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import sys

from analyze_perf import analyze, parse_counters

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import measure


# Construye texto con el formato esperado de perf stat -x ';'. Los valores
# conocidos permiten verificar formulas y validaciones sin acceso a una PMU.
def fixture(cycles=100, instructions=200, misses=10, refs=100, active=100):
    values = dict(zip(('cycles', 'instructions', 'cache-misses', 'cache-references'),
                      (cycles, instructions, misses, refs)))
    return '# perf stat synthetic fixture\n' + '\n'.join(
        f'{v};;{k};100000;{active};;' for k, v in values.items())


# Pruebas del parser: debe aceptar datos validos y rechazar eventos inutilizables.
class ParserTests(unittest.TestCase):
    def test_valid_and_multiplexed(self):
        # Caso con actividad del 75 %. Aprobar exige conservar conteo y
        # porcentaje reportados, sin escalar el contador una segunda vez.
        self.assertEqual(parse_counters(fixture(active=75))['cycles'], (100, 75))

    def test_unavailable_events(self):
        # Eventos no soportados/no contados, incluido espacio final.
        # Cada variante debe lanzar ValueError; no debe convertirse a cero.
        for value in ('<not supported>', '<not counted>', '<not supported> '):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture().replace('100;;cycles', value + ';;cycles'))

    def test_missing_and_duplicate(self):
        # Un reporte truncado pierde eventos; el otro repite cycles.
        # Aprobar exige rechazar ambos mediante ValueError.
        for text in (fixture().split('10;;cache-misses')[0], fixture() + '\n100;;cycles'):
            with self.assertRaises(ValueError):
                parse_counters(text)

    def test_invalid_numbers(self):
        # NaN, infinito, negativos y cero no son ciclos validos para el IPC.
        # Todos deben ser rechazados; cero si puede ser valido en eventos de cache.
        for value in ('nan', 'inf', '-1', '0'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture(cycles=value))

    def test_invalid_active_percent(self):
        # Actividad debe ser finita y estar en (0, 100]. Aprobar exige
        # ValueError para cada porcentaje fuera de ese intervalo o NaN.
        for value in (0, -1, 101, 'nan'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture(active=value))

    def test_inconsistent_cache(self):
        # 101 fallos con 100 referencias viola el criterio del analizador.
        # Debe rechazarse para evitar publicar una tasa incoherente.
        with self.assertRaises(ValueError):
            parse_counters(fixture(misses=101))


# Pruebas de tablas: usan reportes sinteticos para ambas versiones y metadatos.
class ReportTests(unittest.TestCase):
    def setUp(self):
        # Cada prueba recibe un directorio aislado que unittest limpia despues.
        # Dos procesos por version: ciclos 100/300 e instrucciones 200/900.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.metadata = dict(mode='perf', sizes=[1000], perf_runs=2, reps=30)
        self.write_metadata()
        for v in ('scalar', 'vector'):
            (self.path / f'{v}_1000_1.csv').write_text(fixture())
            (self.path / f'{v}_1000_2.csv').write_text(fixture(cycles=300, instructions=900))

    def write_metadata(self):
        (self.path / 'metadata.json').write_text(json.dumps(self.metadata))

    def test_weighted_ipc_and_std(self):
        # Aprobar exige media de ciclos 200, desviacion muestral sqrt(20000),
        # IPC de sumas 1100/400=2.75 y tasa de fallos 10 %.
        # Tambien exige que el informe explicite el alcance del proceso completo.
        row = analyze(self.path)[0]
        self.assertEqual(row[4], 200)
        self.assertAlmostEqual(row[8], 141.421356237)
        self.assertEqual(row[12], 2.75)  # 1100 / 400, no promedio de 2 y 3.
        self.assertEqual(row[13], 10)
        self.assertIn('proceso completo', (self.path / 'perf_report.md').read_text())

    def test_no_partial_report(self):
        # Falta una muestra vectorial: debe fallar y no crear perf_summary.csv.
        (self.path / 'vector_1000_2.csv').unlink()
        with self.assertRaises(OSError):
            analyze(self.path)
        self.assertFalse((self.path / 'perf_summary.csv').exists())

    def test_failed_run_rejected(self):
        # Una ejecucion marcada FAILED no puede analizarse como valida.
        (self.path / 'FAILED.txt').touch()
        with self.assertRaises(ValueError):
            analyze(self.path)

    def test_zero_cache_denominator(self):
        # Cero fallos y referencias: tasa indefinida. Aprobar exige celda
        # vacia en el resultado y N/D en el informe, en lugar de 0 %.
        for p in self.path.glob('*.csv'):
            p.write_text(fixture(misses=0, refs=0))
        self.assertEqual(analyze(self.path)[0][13], '')
        self.assertIn('N/D', (self.path / 'perf_report.md').read_text())

    def test_per_size_reps_and_per_element_columns(self):
        # 1000 elementos * 200 repeticiones = 200000 elementos por proceso
        # La repeticion especifica debe prevalecer sobre reps=30. Aprobar
        # exige los cocientes correctos y las columnas correspondientes.
        self.metadata['perf_reps'] = {'1000': 200}
        self.write_metadata()
        row = analyze(self.path)[0]
        self.assertEqual(row[3], 200)
        self.assertAlmostEqual(row[15], 200 / 200000)          # ciclos medios / (N*reps)
        self.assertAlmostEqual(row[16], 550 / 200000)          # instrucciones medias (200 y 900) / (N*reps)
        self.assertAlmostEqual(row[17], 10 / 200000)           # misses medios / (N*reps)
        report = (self.path / 'perf_report.md').read_text()
        self.assertIn('Ciclos/elem', report)
        self.assertIn('| 1000 | scalar | 2 | 200 |', report)

    def test_legacy_metadata_without_perf_reps(self):
        # Compatibilidad: si falta perf_reps, debe usar reps=30 del formato anterior.
        self.assertEqual(analyze(self.path)[0][3], 30)

    def test_single_sample_no_std(self):
        # Con una muestra no se estima desviacion muestral. Debe quedar vacia,
        # sin inventar desviacion cero ni impedir el resto del analisis.
        self.metadata['perf_runs'] = 1
        self.write_metadata()
        self.assertEqual(analyze(self.path)[0][8], '')


# Pruebas de orquestacion: simulan perf y kernels, sin medir hardware real.
class RunnerTests(unittest.TestCase):
    def test_preflight_failure_and_logs(self):
        # Simula perf instalado pero sin permisos para cycles. Aprobar exige
        # RuntimeError explicativo y conservar el mensaje en preflight.log.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with patch.object(measure.shutil, 'which', return_value='/bin/perf'), \
                 patch.object(measure, 'run', return_value=SimpleNamespace(stdout='perf version test')), \
                 patch.object(measure.subprocess, 'run', return_value=SimpleNamespace(
                     returncode=255, stdout='', stderr='No permission to enable cycles event')):
                with self.assertRaisesRegex(RuntimeError, 'no puede acceder'):
                    measure.check_perf(SimpleNamespace(perf='perf'), directory)
            self.assertIn('No permission', (directory / 'preflight.log').read_text())

    def test_complete_collection_with_synthetic_perf(self):
        # Ejecuta la orquestacion real y el analizador real; solo PMU y kernels se simulan.
        # Dos tamanos, dos versiones y dos procesos: ocho comandos esperados.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'metadata.json').write_text(json.dumps(
                dict(mode='perf', sizes=[16, 1000], perf_runs=2, reps=30)))
            args = SimpleNamespace(perf='perf', sizes=[16, 1000], perf_runs=2, reps=30, seed=123)
            order = []
            real_run = subprocess.run

            def synthetic(command, **kwargs):
                # Solo intercepta perf; el analizador Python se ejecuta realmente.
                if command[0] != 'perf':
                    return real_run(command, **kwargs)
                report = Path(command[command.index('-o') + 1])
                order.append(report.name)
                report.write_text(fixture())
                return SimpleNamespace(returncode=0, stdout='synthetic test', stderr='')

            with patch.object(measure, 'generate'), patch.object(measure, 'verify_size'), \
                 patch.object(measure, 'sample'), patch.object(measure.subprocess, 'run', side_effect=synthetic):
                measure.perf(args, directory, directory)
            # Aprobar exige alternar el orden escalar/vectorial entre procesos,
            # producir el resumen y registrar los ocho comandos completos.
            self.assertEqual(order[:4], ['scalar_16_1.csv', 'vector_16_1.csv',
                                        'vector_16_2.csv', 'scalar_16_2.csv'])
            self.assertTrue((directory / 'perf_summary.csv').exists())
            commands = json.loads((directory / 'commands.json').read_text())
            self.assertEqual(len(commands), 8)
            # Repeticiones escaladas por tamano: N pequeno se limita a PERF_MAX_REPS.
            # Aprobar exige que los comandos usen el ajuste calculado: limite
            # para N=16, 200000 para N=1000 y minimo 30 para N=50000000.
            self.assertEqual({c[-1] for c in commands},
                             {str(measure.perf_reps(16, 30)), str(measure.perf_reps(1000, 30))})
            self.assertEqual(measure.perf_reps(16, 30), measure.PERF_MAX_REPS)
            self.assertEqual(measure.perf_reps(1000, 30), 200000)
            self.assertEqual(measure.perf_reps(50_000_000, 30), 30)  # nunca por debajo de --reps


if __name__ == '__main__':
    # unittest aprueba solo si todas las aserciones y excepciones esperadas
    # se cumplen. Estos resultados validan software, no rendimiento ni la PMU.
    unittest.main()
