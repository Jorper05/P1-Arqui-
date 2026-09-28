#!/usr/bin/env python3
"""Verifica estadisticos y normalizacion float32 contra NumPy y entre versiones."""
import argparse
import math
from pathlib import Path
import struct
import subprocess
import tempfile

import numpy as np

from gen_input import generate, SMALL

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('sum', 'mean', 'var', 'stddev', 'min', 'max')


def read_input(path):
    raw = Path(path).read_bytes()
    if len(raw) < 4:
        raise ValueError(f'{path}: falta N')
    n = struct.unpack('<i', raw[:4])[0]
    if n < 0 or len(raw) != 4 + 4 * n:
        raise ValueError(f'{path}: N o longitud invalida')
    values = np.frombuffer(raw, dtype='<f4', offset=4).copy()
    if not np.all(np.isfinite(values)):
        raise ValueError(f'{path}: contiene NaN o infinito')
    return n, values


def read_summary(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            if key in result:
                raise ValueError(f'{path}: campo duplicado {key}')
            result[key] = float(value)
    if not all(key in result for key in ('n',) + FIELDS):
        raise ValueError(f'{path}: faltan estadisticos')
    if not all(np.isfinite(result[key]) for key in ('n',) + FIELDS):
        raise ValueError(f'{path}: estadisticos no finitos')
    return result


def reference_stats(values):
    if not len(values):
        raise ValueError(
            'N = 0 debe rechazarse antes de ejecutar los kernels'
        )

    with np.errstate(over='raise', invalid='raise', divide='raise'):
        # Referencia independiente: acumular con alta precision y
        # redondear a float32 antes de continuar cada etapa.
        total = np.float32(math.fsum(map(float, values)))
        count = np.float32(len(values))
        mean = np.float32(total / count)

        delta = values - mean
        squares = delta * delta
        squared_sum = np.float32(math.fsum(map(float, squares)))
        var = np.float32(squared_sum / count)
        stddev = np.sqrt(var)

        normalized = (
            values.copy() if stddev == 0 else delta / stddev
        )

    stats = dict(zip(
        FIELDS,
        (total, mean, var, stddev, values.min(), values.max())
    ))
    return stats, normalized


def discrepancy_mask(actual, expected, rtol, atol):
    """Marca errores con tolerancia relativa, o absoluta si la referencia es cero."""
    actual, expected = np.asarray(actual, dtype=np.float64), np.asarray(expected, dtype=np.float64)
    if actual.shape != expected.shape:
        raise ValueError('Las formas de los resultados no coinciden')
    with np.errstate(over='ignore', invalid='ignore'):
        limit = np.where(expected == 0, atol, rtol * np.abs(expected))
        return (~np.isfinite(actual) | ~np.isfinite(expected)
                | (np.abs(actual - expected) > limit))


def close(actual, expected, rtol, atol):
    if np.shape(actual) != np.shape(expected):
        return False
    return not bool(np.any(discrepancy_mask(actual, expected, rtol, atol)))


def normalization_check(values, stats, output):
    """Comprueba la formula float32 con los parametros del propio ejecutable."""
    mean, sigma = np.float32(stats['mean']), np.float32(stats['stddev'])
    if not np.isfinite(mean) or not np.isfinite(sigma) or sigma < 0:
        return False
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        expected = values.copy() if sigma == 0 else (values - mean) / sigma
    return bool(np.all(np.isfinite(output)) and np.all(np.isfinite(expected))
                and np.array_equal(output, expected))


def precision_diagnostic(values, results, ref):
    """Referencia de diagnostico; no cambia el criterio de aceptacion."""
    total = math.fsum(map(float, values))
    mean = total / len(values)
    print('  DIAGNOSTICO: suma con math.fsum; no sustituye la referencia NumPy float32')
    print(f'  suma={total:.17g}, media={mean:.17g}')
    for name, stats in [('NumPy', ref)] + [(name, pair[0]) for name, pair in results.items()]:
        actual = float(np.float32(stats['mean']))
        print(f'  {name}: media={actual:.17g}, error absoluto de media={abs(actual-mean):.9g}')


def compare(values, results, rtol, atol, diagnose=False):
    ref, normalized = reference_stats(values)
    ok = True
    for group, fields in (('sum_array', ('sum',)),
                          ('compute_stats', ('mean', 'var', 'min', 'max', 'stddev'))):
        group_ok = True
        for key in fields:
            checks = [close(stats[key], ref[key], rtol, atol) for stats, _ in results.values()]
            if len(results) == 2:
                a, b = list(results.values())
                checks.append(close(a[0][key], b[0][key], rtol, atol))
            if not all(checks):
                group_ok = False
                print(f'  {key}: Expected={ref[key]:.9g} ' + ' '.join(
                    f'{name}={stats[key]:.9g}' for name, (stats, _) in results.items()))
        print(f'[{"PASS" if group_ok else "FAIL"}] {group}')
        ok &= group_ok
    array_ok = True
    pairs = [(name, output, normalized) for name, (_, output) in results.items()]
    if len(results) == 2:
        a, b = list(results.values())
        pairs.append(('Scalar/AVX2', a[1], b[1]))
    for name, output, expected in pairs:
        pair_ok = close(output, expected, rtol, atol)
        print(f'[{"PASS" if pair_ok else "FAIL"}] normalizacion: {name}' +
              (' entre versiones' if name == 'Scalar/AVX2' else ' contra NumPy'))
        if not pair_ok:
            array_ok = False
            if output.shape == expected.shape:
                bad = np.flatnonzero(discrepancy_mask(output, expected, rtol, atol))
                i = int(bad[0])
                print(f'  {name}: indice={i}, Expected={expected[i]:.9g}, obtenido={output[i]:.9g}, discrepancias={len(bad)}')
            else:
                print(f'  {name}: longitud de salida incorrecta')
    print(f'[{"PASS" if array_ok else "FAIL"}] normalize_array')
    formula_ok = True
    for name, (stats, output) in results.items():
        matched = normalization_check(values, stats, output)
        formula_ok &= matched
        print(f'[{"PASS" if matched else "FAIL"}] {name}: formula con media/stddev propios')
    if diagnose:
        precision_diagnostic(values, results, ref)
    return bool(ok and array_ok and formula_ok)


def load_result(summary, output, n):
    stats = read_summary(summary)
    out_n, values = read_input(output)
    if stats['n'] != n or out_n != n:
        raise ValueError('N de salida/resumen distinto de la entrada')
    return stats, values


def run_case(path, scalar, vector, rtol, atol, diagnose=False):
    n, values = read_input(path)
    print(f'\nCaso: {Path(path).name}, N={n}')
    results = {}
    empty_ok = True
    with tempfile.TemporaryDirectory(prefix='verify-') as directory:
        for name, executable in (('Scalar', scalar), ('AVX2', vector)):
            output = Path(directory) / f'{name}.dat'
            run = subprocess.run([str(executable), str(Path(path).resolve()), str(output), '1'],
                                 capture_output=True, text=True, timeout=60)
            if n == 0:
                controlled = (run.returncode > 0 and 'Error:' in run.stderr
                              and not output.exists() and not Path(str(output) + '.stats.txt').exists())
                print(f'[{"PASS" if controlled else "FAIL"}] {name}: rechazo controlado de N=0 (codigo={run.returncode})')
                empty_ok &= controlled
                continue
            if run.returncode != 0:
                raise ValueError(f'{name}: codigo={run.returncode}, {run.stderr.strip()}')
            results[name] = load_result(str(output) + '.stats.txt', output, n)
    return empty_ok if n == 0 else compare(values, results, rtol, atol, diagnose)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('summary', nargs='?', type=Path)
    parser.add_argument('tolerance', nargs='?', type=float)
    parser.add_argument('--output', type=Path, help='Binario asociado al resumen; se infiere quitando .stats.txt')
    parser.add_argument('--suite', action='store_true', help='Generar y verificar casos reproducibles')
    parser.add_argument('--diagnose', action='store_true', help='Mostrar error de la media frente a math.fsum sin cambiar tolerancias')
    parser.add_argument('--scalar', type=Path, default=ROOT / 'bin/norm_scalar')
    parser.add_argument('--vector', type=Path, default=ROOT / 'bin/norm_vector')
    parser.add_argument('--rtol', type=float, default=1e-4)
    parser.add_argument('--atol', type=float, default=1e-6, help='Tolerancia absoluta solo si la referencia es cero')
    args = parser.parse_args()
    rtol = args.tolerance if args.tolerance is not None else args.rtol
    if not all(np.isfinite(x) and x >= 0 for x in (rtol, args.atol)):
        parser.error('Las tolerancias deben ser finitas y no negativas')
    if args.suite == (args.input is not None):
        parser.error('Indique una entrada o --suite')
    if args.output and not args.summary:
        parser.error('--output requiere un resumen')
    failures = 0
    try:
        if args.summary:
            n, values = read_input(args.input)
            output = args.output or Path(str(args.summary).removesuffix('.stats.txt'))
            result = load_result(args.summary, output, n)
            failures = int(not compare(values, {'Obtenido': result}, rtol, args.atol, args.diagnose))
        else:
            with tempfile.TemporaryDirectory(prefix='verify-inputs-') as directory:
                paths = [args.input] if args.input else []
                if args.suite:
                    jobs = [(n, 'random') for n in SMALL] + [(16, 'constant'), (16, 'edge'), (15, 'edge')]
                    for n, mode in jobs:
                        path = Path(directory) / f'input_{n}_{mode}.dat'
                        generate(n, path, mode, 123)
                        paths.append(path)
                    for name, values in (('negative', -np.arange(1, 18, dtype=np.float32)),
                                         ('zero_sum', np.array([-4, -3, -2, -1, 0, 1, 2, 3, 4], dtype=np.float32))):
                        path = Path(directory) / f'{name}.dat'
                        path.write_bytes(struct.pack('<i', len(values)) + values.astype('<f4').tobytes())
                        paths.append(path)
                for path in paths:
                    try:
                        failures += not run_case(path, args.scalar.resolve(), args.vector.resolve(), rtol, args.atol, args.diagnose)
                    except (OSError, ValueError, FloatingPointError, subprocess.TimeoutExpired) as exc:
                        failures += 1
                        print(f'[FAIL] {path.name}: {exc}')
    except (OSError, ValueError, FloatingPointError) as exc:
        print(f'[FAIL] {exc}')
        return 1
    print(f'\nRESULTADO GENERAL: {"PASA" if failures == 0 else "FALLA"}; casos fallidos={failures}')
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
