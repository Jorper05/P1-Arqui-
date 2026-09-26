#!/usr/bin/env python3
"""Mediciones reproducibles de los ejecutables escalar y AVX2."""
import argparse
import csv
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


def benchmark(args, directory, work):
    # El CSV final se publica solo cuando todas las mediciones terminan.
    rows = []
    with (directory / 'samples.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'version', 'sample', 'kernel_ms'])
        for n in args.sizes:
            source = work / 'input.dat'
            generate(n, source, seed=args.seed)
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
            rows.append([n, args.reps, args.seed, scalar, statistics.stdev(times['scalar']),
                         vector, statistics.stdev(times['vector']), scalar / vector])
            print(f'N={n}: escalar={scalar:.6f} ms, AVX2={vector:.6f} ms, '
                  f'speedup={scalar / vector:.3f}', flush=True)
    with (directory / 'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'samples', 'seed', 'scalar_mean_ms', 'scalar_std_ms',
                         'vector_mean_ms', 'vector_std_ms', 'speedup'])
        writer.writerows(rows)


def perf(args, directory, work):
    if shutil.which(args.perf) is None:
        raise RuntimeError('No se encontro perf. Instale linux-tools compatible con su kernel.')
    for n in args.sizes:
        source = work / 'input.dat'
        generate(n, source, seed=args.seed)
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
            print(f'Contadores: {report}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('benchmark', 'perf'))
    parser.add_argument('--sizes', nargs='+', type=positive, default=[1000, 100000, 1000000, 50000000])
    parser.add_argument('--reps', type=positive, default=30)
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--perf', default='perf')
    args = parser.parse_args()
    if args.mode == 'benchmark' and args.reps < 2:
        parser.error('se requieren al menos dos muestras para calcular la desviacion estandar')
    if args.mode == 'benchmark' and args.reps < 30:
        print('Aviso: prueba rapida; el informe requiere al menos 30 muestras.')
    parent = ROOT / 'output' / args.mode
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=parent))
    print(f'Resultados de esta ejecucion: {directory}', flush=True)
    try:
        with tempfile.TemporaryDirectory(prefix='measure-') as temporary:
            {'benchmark': benchmark, 'perf': perf}[args.mode](args, directory, Path(temporary))
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        (directory / 'FAILED.txt').write_text(str(exc) + '\n')
        print(f'Error: {exc}')
        return 1
    (directory / 'COMPLETE.txt').write_text('Mediciones completadas.\n')
    return 0


if __name__ == '__main__':
