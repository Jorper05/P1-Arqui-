#!/usr/bin/env python3
"""Fase 3: entradas reproducibles, suma NASM escalar/AVX2 y referencia float32."""
import csv
import math
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SIZES = (0, 1, 7, 8, 15, 16)
RTOL = 1e-4


def close(actual, expected):
    # Referencia cero: exigir cero evita ocultar errores de cancelacion.
    return (math.isfinite(actual) and math.isfinite(expected)
            and abs(actual - expected) <= RTOL * abs(expected))


def run(binary, path):
    return subprocess.run([str(ROOT / 'bin' / binary), str(path)],
                          text=True, capture_output=True, timeout=10)


def main():
    folder = ROOT / 'data' / 'fase3'
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2026)
    cases = []
    for n in SIZES:
        ascending = np.arange(1, n + 1, dtype=np.float32)
        cases.extend([
            ('secuencia', ascending),
            ('negativos', -ascending),
            ('constante', np.full(n, 3.25, dtype=np.float32)),
            ('mixtos', np.where(np.arange(n) % 2, -ascending, ascending)),
            ('aleatorios', rng.uniform(-10, 10, n).astype(np.float32)),
        ])
    cases.append(('cancelacion', np.array([1, -1] * 8, dtype=np.float32)))
    cases.append(('magnitud_grande', np.arange(1, 17, dtype=np.float32) * np.float32(1e10)))
    rows = []
    failures = skips = 0
    print('Caso                 N       Escalar          AVX2         NumPy  Correcto')
    for name, values in cases:
        n = len(values)
        path = folder / f'{name}_{n}.dat'
        path.write_bytes(struct.pack('<i', n) + values.astype('<f4').tobytes())
        # Leer el archivo real: ambos ejecutables y NumPy usan los mismos bytes.
        data = np.frombuffer(path.read_bytes(), dtype='<f4', offset=4)
        ref = float(np.sum(data, dtype=np.float32))
        results = [run('sum_scalar', path), run('sum_vector', path)]
        scal = vec = float('nan')
        status = 'PASS'
        try:
            if results[0].returncode != 0:
                raise ValueError(results[0].stderr)
            scal = float(results[0].stdout.strip())
            if not close(scal, ref):
                status = 'FAIL'
            if results[1].returncode == 77:
                skips += 1
                if status == 'PASS':
                    status = 'SKIP_AVX2'
            elif results[1].returncode != 0:
                raise ValueError(results[1].stderr)
            else:
                vec = float(results[1].stdout.strip())
                if not (close(vec, ref) and close(scal, vec)):
                    status = 'FAIL'
        except ValueError as exc:
            status = 'FAIL'
            print(f'  Error {name}/{n}: {exc}', file=sys.stderr)
        failures += status == 'FAIL'
        rows.append([name, n, scal, vec, ref, status])
        print(f'{name:20} {n:2} {scal:13.7g} {vec:13.7g} {ref:13.7g}  {status}')

    # N=0 es suma vacia valida en el kernel; el normalizador debe rechazarlo.
    empty = folder / 'secuencia_0.dat'
    for binary in ('norm_scalar', 'norm_vector'):
        out = folder / f'{binary}_empty.dat'
        out.unlink(missing_ok=True)
        summary = Path(str(out) + '.stats.txt')
        summary.unlink(missing_ok=True)
        result = subprocess.run([str(ROOT / 'bin' / binary), str(empty), str(out)],
                                text=True, capture_output=True, timeout=10)
        ok = (result.returncode > 0 and 'N' in result.stderr
              and not out.exists() and not summary.exists())
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {binary} rechaza N=0 de forma controlada")

    report = folder / 'resultados.csv'
    with report.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['caso', 'N', 'escalar', 'AVX2', 'NumPy', 'correcto'])
        writer.writerows(rows)
    print(f'\n{len(rows)} casos de suma; {failures} fallos; {skips} omisiones AVX2.')
    print(f'Tabla: {report}')
    # Una CPU sin AVX2 no debe generar un exito completo falso.
    return 1 if failures else (77 if skips else 0)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
