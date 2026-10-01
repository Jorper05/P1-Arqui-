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

# perf cuenta el proceso completo (arranque, lectura del archivo, memset). Para que
# el kernel domine esos contadores, cada proceso repite el kernel hasta procesar
# al menos PERF_MIN_ELEMENTS elementos (N * repeticiones), sin bajar de --reps.
PERF_MIN_ELEMENTS = 200_000_000
PERF_MAX_REPS = 1_000_000


def perf_reps(n, minimum):
    return min(PERF_MAX_REPS, max(minimum, math.ceil(PERF_MIN_ELEMENTS / n)))


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
    if 'kernel_cycles' not in fields:
        raise ValueError('El driver no reporta kernel_cycles; recompile con make clean && make')
    cycles = float(fields['kernel_cycles'])
    if not all(math.isfinite(v) and v > 0 for v in (elapsed, cycles)):
        raise ValueError('El tiempo y los ciclos del kernel deben ser finitos y mayores que cero')
    return elapsed, cycles


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
        writer.writerow(['n', 'version', 'sample', 'kernel_ms', 'kernel_cycles'])
        for n in args.sizes:
            source = work / 'input.dat'
            generate(n, source, seed=args.seed, random_limit=1000.0)
            verify_size(source, n, directory)
            times = {'scalar': [], 'vector': []}
            cycles = {'scalar': [], 'vector': []}
            for version in times:
                sample(ROOT / f'bin/norm_{version}', source, work / f'{version}.dat')
            for i in range(args.reps):
                # Alternar el orden reduce el sesgo de ejecutar siempre uno primero.
                order = ('scalar', 'vector') if i % 2 == 0 else ('vector', 'scalar')
                for version in order:
                    elapsed, ticks = sample(ROOT / f'bin/norm_{version}', source, work / f'{version}.dat')
                    times[version].append(elapsed)
                    cycles[version].append(ticks)
                    writer.writerow([n, version, i + 1, elapsed, ticks])
                stream.flush()
            scalar, vector = (statistics.mean(times[v]) for v in ('scalar', 'vector'))
            c_scalar, c_vector = (statistics.mean(cycles[v]) for v in ('scalar', 'vector'))
            print(f'N={n}: escalar={scalar:.6f} ms ({c_scalar:.0f} ciclos TSC), '
                  f'AVX2={vector:.6f} ms ({c_vector:.0f} ciclos TSC), '
                  f'speedup={scalar / vector:.3f}', flush=True)
    run([sys.executable, ROOT / 'benchmark/analyze_results.py', directory])


def perf_command(args, report, command):
    # Ciclos e instrucciones comparten grupo para que el IPC use el mismo intervalo.
    return [args.perf, 'stat', '--no-big-num', '-x', ';', '-o', str(report),
            '-e', '{cycles,instructions},cache-misses,cache-references',
            '--', *map(str, command)]


def check_perf(args, directory):
    if shutil.which(args.perf) is None:
        raise RuntimeError('No se encontro perf. Instale linux-tools compatible con su kernel '
                           'o indique make perf PERF=/ruta/al/perf.')
    (directory / 'perf_version.txt').write_text(run([args.perf, '--version']).stdout)
    setting = Path('/proc/sys/kernel/perf_event_paranoid')
    if setting.exists():
        (directory / 'perf_event_paranoid.txt').write_text(setting.read_text())
    report = directory / 'preflight.csv'
    result = subprocess.run(perf_command(args, report, [sys.executable, '-c',
                            'print(sum(range(1000000)))']), capture_output=True,
                            text=True, timeout=60, env={**os.environ, 'LC_ALL': 'C'})
    (directory / 'preflight.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('perf no puede acceder a los eventos solicitados. Revise preflight.log '
                           'y preflight.csv: permisos, compatibilidad del ejecutable o PMU de la VM. '
                           'No se modifico la configuracion del sistema.')
    parse_perf_report(report)


def parse_perf_report(report):
    # El analizador tambien puede ejecutarse por separado sobre los CSV conservados.
    if str(ROOT / 'benchmark') not in sys.path:
        sys.path.insert(0, str(ROOT / 'benchmark'))
    from analyze_perf import parse_counters
    return parse_counters(report.read_text())


def perf(args, directory, work):
    commands = []
    for n in args.sizes:
        source = work / 'input.dat'
        generate(n, source, seed=args.seed)
        verify_size(source, n, directory)
        for version in ('scalar', 'vector'):
            sample(ROOT / f'bin/norm_{version}', source, work / f'{version}.dat')
        reps = perf_reps(n, args.reps)
        print(f'perf N={n}: {reps} repeticiones del kernel por proceso', flush=True)
        for index in range(1, args.perf_runs + 1):
            order = ('scalar', 'vector') if index % 2 else ('vector', 'scalar')
            for version in order:
                report = directory / f'{version}_{n}_{index}.csv'
                command = perf_command(args, report, [ROOT / f'bin/norm_{version}',
                                       source, work / f'{version}.dat', reps])
                commands.append(command)
                (directory / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
                result = subprocess.run(command, capture_output=True, text=True, timeout=600,
                                        env={**os.environ, 'LC_ALL': 'C'})
                report.with_suffix('.log').write_text(result.stdout + result.stderr)
                if result.returncode:
                    raise RuntimeError(f'perf fallo para {version}, N={n}, muestra={index}. '
                                       f'Revise {report} y su .log; no se publicara un resumen.')
                parse_perf_report(report)
                print(f'Contadores: {report}', flush=True)
    run([sys.executable, ROOT / 'benchmark/analyze_perf.py', directory])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('benchmark', 'perf'))
    parser.add_argument('--sizes', nargs='+', type=positive, default=[1000, 100000, 1000000, 50000000])
    parser.add_argument('--reps', type=positive, default=30)
    parser.add_argument('--seed', type=int, default=123)
    parser.add_argument('--perf', default='perf')
    parser.add_argument('--perf-runs', type=positive, default=3,
                        help='procesos independientes por version y tamano (solo perf)')
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
            'mode': args.mode, 'perf_runs': args.perf_runs,
            'sample_scope': ('kernel_ms y kernel_cycles (TSC) del driver; una repeticion '
                             'cronometrada por proceso, tras una llamada de calentamiento'
                             if args.mode == 'benchmark' else
                             'contadores del proceso completo; repeticiones del kernel por '
                             'tamano indicadas en perf_reps'),
            'standard_deviation': 'muestral (ddof=1)',
            'correctness': 'suite pequena y cada tamano; rtol=1e-4, atol=1e-6 solo referencia cero',
            'perf_scope': ('proceso completo, incluida E/S; las repeticiones se escalan por tamano '
                           f'(N*reps >= {PERF_MIN_ELEMENTS}) para que el kernel domine los contadores'),
            'perf_reps': {str(n): perf_reps(n, args.reps) for n in args.sizes},
            'binaries_sha256': {v: hashlib.sha256((ROOT / f'bin/norm_{v}').read_bytes()).hexdigest()
                                for v in ('scalar', 'vector')},
        }
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
        metadata['commit'] = commit.stdout.strip() if commit.returncode == 0 else None
        (directory / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        for label, command in [('cpu', ['lscpu']), ('compiler', ['gcc', '--version'])]:
            if shutil.which(command[0]):
                (directory / f'{label}.txt').write_text(run(command).stdout)
        if args.mode == 'perf':
            check_perf(args, directory)
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
