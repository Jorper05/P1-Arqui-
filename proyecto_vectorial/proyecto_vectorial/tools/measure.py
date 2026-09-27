#!/usr/bin/env python3
"""Mediciones reproducibles de los ejecutables escalar y AVX2."""
import argparse
import csv
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile

from gen_input import generate, MAX_N

ROOT = Path(__file__).resolve().parents[1]


def positive(value):
    number = int(value)
    if not 1 <= number <= MAX_N:
        raise argparse.ArgumentTypeError(f'indique un entero entre 1 y {MAX_N}')
    return number


def run(command, **kwargs):
    result = subprocess.run([str(item) for item in command], capture_output=True,
                            text=True, timeout=600, **kwargs)
    if result.returncode:
        raise RuntimeError(f'{command[0]} termino con codigo {result.returncode}: '
                           f'{result.stderr.strip()}')
    return result


def sample(binary, source, destination):
    summary = Path(str(destination) + '.stats.txt')
    summary.unlink(missing_ok=True)
    run([binary, source, destination, '1'])
    fields = dict(line.split('=', 1) for line in summary.read_text().splitlines())
    elapsed = float(fields['kernel_ms'])
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError('El tiempo del kernel debe ser finito y mayor que cero')
    return elapsed


def verify_size(source, n, directory):
    result = subprocess.run([sys.executable, ROOT / 'tools/verify_reference.py', source],
                            capture_output=True, text=True, timeout=600)
    report = directory / f'verification_{n}.log'
    report.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f'N={n}: resultados fuera de tolerancia; consulte {report}. '
                           'No se publicara un resumen de rendimiento valido.')


def benchmark(args, directory, work):
    # El CSV final se publica solo cuando todas las mediciones terminan.
    with (directory / 'samples.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'version', 'sample', 'kernel_ms'])
        for n in args.sizes:
            source = work / 'input.dat'
            generate(n, source, seed=args.seed)
            verify_size(source, n, directory)
            times = {'scalar': [], 'vector': []}
            for version in times:
                sample(ROOT / f'bin/norm_{version}', source, work / f'{version}.dat')
            for i in range(args.reps):
                # Alternar el orden reduce el sesgo de ejecutar siempre uno primero.
                order = ('scalar', 'vector') if i % 2 == 0 else ('vector', 'scalar')
                for version in order:
                    elapsed = sample(ROOT / f'bin/norm_{version}', source, work / f'{version}.dat')
                    times[version].append(elapsed)
                    writer.writerow([n, version, i + 1, elapsed])
                stream.flush()
            scalar, vector = (statistics.mean(times[v]) for v in ('scalar', 'vector'))
            print(f'N={n}: escalar={scalar:.6f} ms, AVX2={vector:.6f} ms, '
                  f'speedup={scalar / vector:.3f}', flush=True)
    run([sys.executable, ROOT / 'benchmark/analyze_results.py', directory])


def perf(args, directory, work):
    if shutil.which(args.perf) is None:
        raise RuntimeError('No se encontro perf. Instale linux-tools compatible con su kernel.')
    rows = []
    for n in args.sizes:
        source = work / 'input.dat'
        generate(n, source, seed=args.seed)
        verify_size(source, n, directory)
        for version in ('scalar', 'vector'):
            report = directory / f'{version}_{n}.csv'
            result = subprocess.run(
                [args.perf, 'stat', '-x', ';', '-o', str(report), '-e',
                 'cycles,instructions,cache-misses,cache-references',
                 str(ROOT / f'bin/norm_{version}'), str(source),
                 str(work / f'{version}.dat'), str(args.reps)],
                capture_output=True, text=True, timeout=600,
                env={**os.environ, 'LC_ALL': 'C'})
            (directory / f'{version}_{n}.log').write_text(result.stdout + result.stderr)
            content = report.read_text() if report.exists() else ''
            if result.returncode or not content or '<not supported>' in content or '<not counted>' in content:
                raise RuntimeError(f'perf no pudo medir todos los eventos para {version}. '
                                   f'Revise {directory} y los permisos de contadores del sistema. '
                                   f'{result.stderr.strip()}')
            counters = {}
            for line in csv.reader(content.splitlines(), delimiter=';'):
                if len(line) >= 3 and line[2].strip() in ('cycles', 'instructions', 'cache-misses', 'cache-references'):
                    counters[line[2].strip()] = float(line[0].strip())
            if len(counters) != 4 or any(not math.isfinite(v) or v < 0 for v in counters.values()):
                raise ValueError('Contadores incompletos o invalidos')
            cycles, refs = counters['cycles'], counters['cache-references']
            rows.append([n, version, args.reps, cycles, counters['instructions'],
                         counters['cache-misses'], refs,
                         counters['instructions'] / cycles if cycles else '',
                         100 * counters['cache-misses'] / refs if refs else ''])
            print(f'Contadores: {report}', flush=True)
    with (directory / 'perf_summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'version', 'kernel_reps', 'cycles', 'instructions',
                         'cache_misses', 'cache_references', 'ipc', 'cache_miss_percent'])
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('benchmark', 'perf'))
    parser.add_argument('--sizes', nargs='+', type=positive, default=[1000, 100000, 1000000, 50000000])
    parser.add_argument('--reps', type=positive, default=30)
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--perf', default='perf')
    parser.add_argument('--results-dir', type=Path)
    args = parser.parse_args()
    if args.mode == 'benchmark' and args.reps < 2:
        parser.error('se requieren al menos dos muestras para calcular la desviacion estandar')
    if args.mode == 'benchmark' and args.reps < 30:
        print('Aviso: prueba rapida; el informe requiere al menos 30 muestras.')
    if len(set(args.sizes)) != len(args.sizes):
        parser.error('no repita tamanos')
    parent = args.results_dir or ROOT / 'output' / args.mode
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    print(f'Resultados de esta ejecucion: {directory}', flush=True)
    try:
        metadata = {
            'utc': datetime.now(timezone.utc).isoformat(),
            'platform': platform.platform(), 'python': sys.version,
            'sizes': args.sizes, 'reps': args.reps, 'seed': args.seed,
            'mode': args.mode, 'sample_scope': 'kernel_ms del driver; una repeticion por proceso',
            'standard_deviation': 'muestral (ddof=1)',
            'correctness': 'suite pequena y cada tamano; rtol=1e-4, atol=1e-6 solo referencia cero',
            'perf_scope': 'proceso completo, incluida E/S',
            'binaries_sha256': {v: hashlib.sha256((ROOT / f'bin/norm_{v}').read_bytes()).hexdigest()
                                for v in ('scalar', 'vector')},
        }
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
        metadata['commit'] = commit.stdout.strip() if commit.returncode == 0 else None
        (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        for label, command in [('cpu', ['lscpu']), ('compiler', ['gcc', '--version'])]:
            if shutil.which(command[0]):
                (directory / f'{label}.txt').write_text(run(command).stdout)
        print('Verificando ambas versiones contra NumPy antes de medir...', flush=True)
        verification = subprocess.run([sys.executable, ROOT / 'tools/verify_reference.py', '--suite'],
                                      capture_output=True, text=True, timeout=600)
        (directory / 'verification.log').write_text(verification.stdout + verification.stderr)
        if verification.returncode:
            raise RuntimeError('La verificacion fallo; consulte verification.log. No se midio rendimiento.')
        with tempfile.TemporaryDirectory(prefix='measure-') as temporary:
            {'benchmark': benchmark, 'perf': perf}[args.mode](args, directory, Path(temporary))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        (directory / 'FAILED.txt').write_text(str(exc) + '\n')
        print(f'Error: {exc}')
        return 1
    (directory / 'COMPLETE.txt').write_text('Mediciones completadas.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

