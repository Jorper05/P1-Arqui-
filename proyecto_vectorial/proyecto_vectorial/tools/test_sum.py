#!/usr/bin/env python3
""" comparar sum_array escalar, AVX2 y NumPy."""
import os
import struct
import subprocess
import sys
import math
import tempfile
import numpy as np

# N=0: suma vacia; N=1: elemento unico; 7/8 y 15/16: fronteras de
# bloques AVX de ocho floats, con y sin remanente escalar.
CASES = [0, 1, 7, 8, 15, 16]
# Limite relativo habitual; tambien es el limite absoluto cerca de cero.
TOL = 1e-4
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generar(n):
    # Carpeta propia para no reemplazar entradas existentes de otras fases.
    # Los archivos input_N.dat de esta carpeta si se regeneran en cada prueba.
    carpeta = os.path.join(ROOT, "data", "simple")
    os.makedirs(carpeta, exist_ok=True)
    archivo = os.path.join(carpeta, f"input_{n}.dat")
    # Semilla fija 123: permite reproducir los datos en el mismo entorno.
    # La generacion debe terminar correctamente antes de comparar kernels.
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "gen_input.py"),
         str(n), archivo, "random", "123"],
        check=True, capture_output=True, text=True, timeout=30
    )
    return archivo


def referencia_numpy(path):
    # Valida el formato binario: int32 N y exactamente N float32 little endian.
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
    # Referencia de los casos basicos: suma NumPy con acumulacion float32.
    # La conversion final a float de Python no cambia la precision ya calculada.
    return float(np.sum(datos, dtype=np.float32))


def ejecutar(programa, archivo):
    # Los auxiliares C llaman sum_array y validan entrada intacta y suma finita.
    # Aqui se exige codigo cero y se lee la suma para compararla numericamente.
    resultado = subprocess.run(
        [programa, archivo], capture_output=True, text=True, timeout=10
    )
    if resultado.returncode == 77:
        # Sin AVX2 la comparacion queda incompleta y no se considera aprobada.
        raise RuntimeError("AVX2 no disponible: no se completo la comparacion")
    if resultado.returncode != 0:
        detalle = resultado.stderr.strip() or f"codigo {resultado.returncode}"
        raise RuntimeError(f"{os.path.basename(programa)}: {detalle}")
    return float(resultado.stdout.strip())


def error_relativo(valor, referencia):
    # Un resultado no finito siempre falla el criterio de tolerancia.
    if not math.isfinite(valor) or not math.isfinite(referencia):
        return math.inf
    # Cerca de cero se utiliza error absoluto; N=0 se verifica aparte.
    # Evita dividir por una referencia nula o demasiado pequena.
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
                # Aprobar la suma vacia exige cero exacto en ambas versiones
                # y en NumPy; no aplica la tolerancia de los otros tamanos.
                ok = (esc == 0.0 and avx == 0.0 and ref == 0.0)
            else:
                # Tres acuerdos obligatorios: escalar/NumPy, AVX2/NumPy y
                # AVX2/escalar. Cada error debe ser <= 1e-4, relativo salvo
                # que la referencia de esa comparacion este cerca de cero.
                ok = (error_relativo(esc, ref) <= TOL
                      and error_relativo(avx, ref) <= TOL
                      and error_relativo(avx, esc) <= TOL)
            print(f"{n:>4} {esc:>15.9g} {avx:>15.9g} {ref:>15.9g} "
                  f"{'PASA' if ok else 'FALLA':>10}")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            # Un archivo invalido, error de proceso o timeout cuenta como
            # caso no aprobado; continua con los demas tamanos basicos.
            detalle = str(exc)
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                detalle += "\n" + exc.stderr.strip()
            print(f"{n:>4} ERROR: {detalle}")
            ok = False
        general = general and ok
    # Cancelacion en un carril, entre carriles y con remanente escalar.
    # Busca detectar perdida de valores pequenos al sumar magnitudes grandes:
    # N=3 tiene referencia 1, N=24 referencia 8 y N=25 referencia 11.
    # Son exigencias de precision adicionales: una suma float32 ordinaria
    # puede perder esos valores dependiendo de su orden de acumulacion.
    with tempfile.TemporaryDirectory(prefix='sum-cancel-') as directory:
        cases = ([1e8, 1, -1e8],
                 [1e8] * 8 + [1] * 8 + [-1e8] * 8,
                 [1e8] * 8 + [1] * 8 + [-1e8] * 8 + [3])
        for index, values in enumerate(cases):
            data = np.asarray(values, dtype='<f4')
            path = os.path.join(directory, f'cancel_{index}.dat')
            with open(path, 'wb') as stream:
                stream.write(struct.pack('<i', len(data)) + data.tobytes())
            # Referencia distinta de los casos basicos: math.fsum acumula
            # con mayor precision los datos float32 y solo al final se
            # redondea a float32. No es np.sum con acumulacion float32.
            expected = float(np.float32(math.fsum(map(float, data))))
            esc, avx = ejecutar(scalar, path), ejecutar(vector, path)
            # Aprobar exige igualdad exacta de ambas versiones y referencia,
            # sin TOL. Una excepcion en este bloque termina el script, pues
            # no esta dentro del try/except de los casos basicos anteriores.
            ok = esc == avx == expected
            general &= ok
            print(f'Cancelacion N={len(data)}: escalar={esc}, AVX2={avx}, esperado={expected}: '
                  f'{"PASA" if ok else "FALLA"}')
    print()
    # Codigo cero solo si pasan todos los casos basicos y de cancelacion.
    if general:
        print("TODAS LAS PRUEBAS PASAN")
        return 0
    print("EXISTEN PRUEBAS FALLIDAS O NO COMPLETADAS")
    return 1


if __name__ == "__main__":
    sys.exit(main())
