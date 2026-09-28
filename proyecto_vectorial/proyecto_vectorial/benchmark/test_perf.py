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


def fixture(cycles=100, instructions=200, misses=10, refs=100, active=100):
    values = dict(zip(('cycles', 'instructions', 'cache-misses', 'cache-references'),
                      (cycles, instructions, misses, refs)))
    return '# perf stat synthetic fixture\n' + '\n'.join(
        f'{v};;{k};100000;{active};;' for k, v in values.items())


class ParserTests(unittest.TestCase):
    def test_valid_and_multiplexed(self):
        self.assertEqual(parse_counters(fixture(active=75))['cycles'], (100, 75))

    def test_unavailable_events(self):
        for value in ('<not supported>', '<not counted>', '<not supported> '):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture().replace('100;;cycles', value + ';;cycles'))

    def test_missing_and_duplicate(self):
        for text in (fixture().split('10;;cache-misses')[0], fixture() + '\n100;;cycles'):
            with self.assertRaises(ValueError):
                parse_counters(text)

    def test_invalid_numbers(self):
        for value in ('nan', 'inf', '-1', '0'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture(cycles=value))

    def test_invalid_active_percent(self):
        for value in (0, -1, 101, 'nan'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_counters(fixture(active=value))

    def test_inconsistent_cache(self):
        with self.assertRaises(ValueError):
            parse_counters(fixture(misses=101))


class ReportTests(unittest.TestCase):
    def setUp(self):
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
        row = analyze(self.path)[0]
        self.assertEqual(row[4], 200)
        self.assertAlmostEqual(row[8], 141.421356237)
        self.assertEqual(row[12], 2.75)  # 1100 / 400, no promedio de 2 y 3.
        self.assertEqual(row[13], 10)
        self.assertIn('proceso completo', (self.path / 'perf_report.md').read_text())

    def test_no_partial_report(self):
        (self.path / 'vector_1000_2.csv').unlink()
        with self.assertRaises(OSError):
            analyze(self.path)
        self.assertFalse((self.path / 'perf_summary.csv').exists())

    def test_failed_run_rejected(self):
        (self.path / 'FAILED.txt').touch()
        with self.assertRaises(ValueError):
            analyze(self.path)

    def test_zero_cache_denominator(self):
        for p in self.path.glob('*.csv'):
            p.write_text(fixture(misses=0, refs=0))
        self.assertEqual(analyze(self.path)[0][13], '')
        self.assertIn('N/D', (self.path / 'perf_report.md').read_text())

    def test_single_sample_no_std(self):
        self.metadata['perf_runs'] = 1
        self.write_metadata()
        self.assertEqual(analyze(self.path)[0][8], '')


class RunnerTests(unittest.TestCase):
    def test_preflight_failure_and_logs(self):
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
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'metadata.json').write_text(json.dumps(
                dict(mode='perf', sizes=[16, 1000], perf_runs=2, reps=30)))
            args = SimpleNamespace(perf='perf', sizes=[16, 1000], perf_runs=2, reps=30, seed=123)
            order = []
            real_run = subprocess.run

            def synthetic(command, **kwargs):
                if command[0] != 'perf':
                    return real_run(command, **kwargs)
                report = Path(command[command.index('-o') + 1])
                order.append(report.name)
                report.write_text(fixture())
                return SimpleNamespace(returncode=0, stdout='synthetic test', stderr='')

            with patch.object(measure, 'generate'), patch.object(measure, 'verify_size'), \
                 patch.object(measure, 'sample'), patch.object(measure.subprocess, 'run', side_effect=synthetic):
                measure.perf(args, directory, directory)
            self.assertEqual(order[:4], ['scalar_16_1.csv', 'vector_16_1.csv',
                                        'vector_16_2.csv', 'scalar_16_2.csv'])
            self.assertTrue((directory / 'perf_summary.csv').exists())
            self.assertEqual(len(json.loads((directory / 'commands.json').read_text())), 8)


if __name__ == '__main__':
    unittest.main()
