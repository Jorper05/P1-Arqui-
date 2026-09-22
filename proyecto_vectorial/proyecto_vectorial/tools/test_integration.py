#!/usr/bin/env python3
"""Prueba cada funcion NASM por separado y luego la integracion con el driver."""
import argparse
from pathlib import Path
import struct
import subprocess
import tempfile

import numpy as np

from verify_reference import ROOT, close, reference_stats, run_case


def cases():
    rng = np.random.default_rng(123)
    # Todos los remanentes posibles, ademas de los tamanos requeridos.
    for n in sorted(set(range(18)) | {23, 24, 31, 32, 33, 1000}):
        yield f'random_{n}', rng.uniform(-100, 100, n).astype(np.float32)
    yield 'negative', -np.arange(1, 18, dtype=np.float32)
    yield 'zero_sum', np.arange(-4, 5, dtype=np.float32)
    for n in (1, 7, 8, 15, 16, 17):
        yield f'constant_{n}', np.full(n, 3.5, dtype=np.float32)
    yield 'zeros', np.zeros(16, dtype=np.float32)
    # Magnitudes grandes cuyo cuadrado todavia cabe en float32.
    yield 'extreme', np.array([-1e10, 1e10, -1e9, 1e9, -3, 4, 0, 2, -2], dtype=np.float32)
    yield 'tail_min', np.array([1] * 15 + [-100], dtype=np.float32)
    yield 'tail_max', np.array([-1] * 15 + [100], dtype=np.float32)


def execute(binary, mode, path, parameters):
    result = subprocess.run([str(binary), mode, str(path), *parameters],
                            capture_output=True, text=True, timeout=15)
    if result.returncode == 77:
        raise ValueError('AVX2 no disponible; validacion incompleta')
    if result.returncode:
        raise ValueError(f'codigo={result.returncode}: {result.stderr.strip()}')
    return np.array([float(value) for value in result.stdout.split()], dtype=np.float64)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('all', 'scalar-stats', 'scalar-normalize',
                                           'vector-stats', 'vector-normalize', 'driver'), default='all')
    args = parser.parse_args()
    failures = checks = 0
    stages = [('scalar-stats', 'scalar', 'stats'),
              ('scalar-normalize', 'scalar', 'normalize'),
              ('vector-stats', 'vector', 'stats'),
              ('vector-normalize', 'vector', 'normalize')]
    cache = {}
    with tempfile.TemporaryDirectory(prefix='integration-') as directory:
        inputs = []
        for name, values in cases():
            path = Path(directory) / f'{name}.dat'
            path.write_bytes(struct.pack('<i', len(values)) + values.astype('<f4').tobytes())
            inputs.append((name, values, path))
        for stage, version, mode in stages:
            if args.stage not in ('all', stage):
                continue
            print(f'\n{stage}', flush=True)
            for name, values, path in inputs:
                if len(values):
                    ref, _ = reference_stats(values)
                else:
                    ref = dict(mean=0, var=0, min=0, max=0, stddev=0)
                jobs = [('stats', [], np.array([ref[k] for k in ('mean', 'var', 'min', 'max')]))]
                if mode == 'normalize':
                    jobs = []
                    # Parametros de NumPy: no depende de compute_stats NASM.
                    for label, mean, sigma in (('reference', ref['mean'], ref['stddev']),
                                               ('explicit', np.float32(1.25), np.float32(2.5)),
                                               ('zero_sigma', np.float32(7), np.float32(0))):
                        expected = values.copy() if sigma == 0 else (values - mean) / sigma
                        jobs.append((label, [format(float(mean), '.9g'), format(float(sigma), '.9g')], expected))
                for label, parameters, expected in jobs:
                    checks += 1
                    key = (mode, name, label)
                    try:
                        actual = execute(ROOT / f'bin/test_kernels_{version}', mode, path, parameters)
                        if not close(actual, expected, 1e-4, 1e-6):
                            raise ValueError(f'difiere de NumPy: obtenido={actual[:4]}, esperado={expected[:4]}')
                        if version == 'vector' and key in cache and not close(actual, cache[key], 1e-4, 1e-6):
                            raise ValueError('difiere del resultado escalar')
                        if version == 'scalar':
                            cache[key] = actual
                        print(f'[PASS] {name}/{label}')
                    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                        failures += 1
                        print(f'[FAIL] {name}/{label}: {exc}')
        if args.stage in ('all', 'driver'):
            print('\nIntegracion con driver y archivos', flush=True)
            for name, values, path in inputs:
                checks += 1
                try:
                    if not run_case(path, ROOT / 'bin/norm_scalar', ROOT / 'bin/norm_vector', 1e-4, 1e-6):
                        failures += 1
                except (OSError, ValueError, FloatingPointError, subprocess.TimeoutExpired) as exc:
                    failures += 1
                    print(f'[FAIL] {name}: {exc}')
    print(f'\nRESULTADO: {"PASA" if not failures else "FALLA"}; comprobaciones={checks}; fallos={failures}')
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
