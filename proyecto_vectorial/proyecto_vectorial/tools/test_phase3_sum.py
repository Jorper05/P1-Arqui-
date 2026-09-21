#!/usr/bin/env python3
""" comparar sum_array escalar, AVX2 y NumPy."""
import os
import struct
import subprocess
import sys
import math
import numpy as np

CASES = [0, 1, 7, 8, 15, 16]
TOL = 1e-4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generar(n):
    # Carpeta propia para no reemplazar entradas existentes de otras fases.
    carpeta = os.path.join(ROOT, "data", "fase3_simple")
    os.makedirs(carpeta, exist_ok=True)
    archivo = os.path.join(carpeta, f"input_{n}.dat")
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "gen_input.py"),
         str(n), archivo, "random", "123"],
        check=True, capture_output=True, text=True, timeout=30
    )
    return archivo


def referencia_numpy(path):
    with open(path, "rb") as f:
        cabecera = f.read(4)
        if len(cabecera) != 4:
            raise ValueError("Archivo invalido: falta N")
        n = struct.unpack("<i", cabecera)[0]
        if n < 0:
            raise ValueError("Archivo invalido: N negativo")
        contenido = f.read()
    if len(contenido) != 4 * n:
        raise ValueError("La longitud del archivo no coincide con N")
    datos = np.frombuffer(contenido, dtype="<f4")
    if not np.all(np.isfinite(datos)):
        raise ValueError("La entrada contiene NaN o infinito")
    return float(np.sum(datos, dtype=np.float32))


def ejecutar(programa, archivo):
    resultado = subprocess.run(
        [programa, archivo], capture_output=True, text=True, timeout=10
    )
    if resultado.returncode == 77:
        raise RuntimeError("AVX2 no disponible: no se completo la comparacion")
    if resultado.returncode != 0:
        detalle = resultado.stderr.strip() or f"codigo {resultado.returncode}"
        raise RuntimeError(f"{os.path.basename(programa)}: {detalle}")
    return float(resultado.stdout.strip())


def error_relativo(valor, referencia):
    if not math.isfinite(valor) or not math.isfinite(referencia):
        return math.inf
    # Cerca de cero se utiliza error absoluto; N=0 se verifica aparte.
    if abs(referencia) < 1e-12:
        return abs(valor - referencia)
    return abs(valor - referencia) / abs(referencia)


def main():
    scalar = os.path.join(ROOT, "bin", "test_sum_scalar")
    vector = os.path.join(ROOT, "bin", "test_sum_vector")
    print(f"{'N':>4} {'Escalar':>15} {'AVX2':>15} {'NumPy':>15} {'Correcto':>10}")
    print("-" * 70)
    general = True
    for n in CASES:
        try:
            archivo = generar(n)
            ref = referencia_numpy(archivo)
            esc = ejecutar(scalar, archivo)
            avx = ejecutar(vector, archivo)
            if n == 0:
                ok = (esc == 0.0 and avx == 0.0 and ref == 0.0)
            else:
                ok = (error_relativo(esc, ref) <= TOL
                      and error_relativo(avx, ref) <= TOL
                      and error_relativo(avx, esc) <= TOL)
            print(f"{n:>4} {esc:>15.9g} {avx:>15.9g} {ref:>15.9g} "
                  f"{'PASA' if ok else 'FALLA':>10}")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            detalle = str(exc)
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                detalle += "\n" + exc.stderr.strip()
            print(f"{n:>4} ERROR: {detalle}")
            ok = False
        general = general and ok
    print()
    if general:
        print("TODAS LAS PRUEBAS PASAN")
        return 0
    print("EXISTEN PRUEBAS FALLIDAS O NO COMPLETADAS")
    return 1


if __name__ == "__main__":
    sys.exit(main())
