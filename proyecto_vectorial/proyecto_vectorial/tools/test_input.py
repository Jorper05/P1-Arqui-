#!/usr/bin/env python3
"""Valida el generador sin depender de kernels NASM ni de NumPy."""
import argparse
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

# Ejecuta el generador situado junto a este archivo con el mismo Python.
GEN = Path(__file__).with_name("gen_input.py")
# N=0 comprueba el archivo con solo cabecera; N=1 comprueba un unico dato.
# 7/8 y 15/16 cubren fronteras de grupos de ocho elementos; 1000 es un
# caso ordinario. Aqui se valida el formato, no la ejecucion de AVX2.
SMALL = (0, 1, 7, 8, 15, 16, 1000)
# Pruebas opcionales de volumen, hasta un archivo de 200 000 004 bytes.
LARGE = (100_000, 1_000_000, 50_000_000)

# Los criterios usan assert: ejecutar sin -O ni PYTHONOPTIMIZE, pues Python
# puede eliminar estas comprobaciones cuando activa la optimizacion.


def run(*args):
    # Captura stdout/stderr y codigo de salida para evaluar exito o rechazo.
    # El limite de 180 segundos evita esperar indefinidamente una generacion.
    return subprocess.run([sys.executable, str(GEN), *map(str, args)],
                          capture_output=True, text=True, timeout=180)


def check_file(path, n, mode="random"):
    # Aprobar exige exactamente 4 bytes de cabecera + N floats de 4 bytes.
    assert path.stat().st_size == 4 + 4*n, f"Longitud incorrecta: {path}"
    # Reconstruye la secuencia esperada con la misma semilla y parametros.
    # Compara bytes float32 exactos; no emplea tolerancias numericas.
    rng = random.Random(123)
    edge = (-1e6, 1e6, 0.0, -0.0001, 0.0001, -1.0, 1.0)
    with path.open("rb") as stream:
        # La cabecera debe codificar N como int32 little endian.
        assert stream.read(4) == struct.pack("<i", n), "Cabecera incorrecta"
        # Bloques distintos al generador para comprobar continuidad entre bloques.
        # El generador usa 65 536; esta lectura usa 100 003. Se revisan TODOS
        # los elementos sin cargar el archivo completo en memoria.
        for start in range(0, n, 100_003):
            count = min(100_003, n - start)
            if mode == "random":
                # Comprueba la secuencia uniforme [-100, 100] con semilla 123.
                expected = [rng.uniform(-100, 100) for _ in range(count)]
            elif mode == "constant":
                # Cada elemento debe ser exactamente 5.0 en float32.
                expected = [5.0] * count
            else:
                # El patron debe continuar por indice global sin reiniciarse
                # al comenzar un nuevo bloque de escritura o lectura.
                expected = [edge[i % 7] for i in range(start, start + count)]
            assert stream.read(4*count) == struct.pack(f"<{count}f", *expected), f"Datos incorrectos: {path}, bloque {start}"
        # Tras leer N elementos debe alcanzarse EOF sin bytes adicionales.
        assert stream.read(1) == b"", "Bytes sobrantes"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large", action="store_true", help="incluye 50 millones de valores")
    args = parser.parse_args()
    # Aisla todos los archivos de prueba y los elimina al terminar.
    with tempfile.TemporaryDirectory(prefix="input_test_") as temp:
        root = Path(temp)
        # Casos aleatorios basicos y N=65 537: cruza el bloque de 65 536
        # del generador y deja un elemento pendiente. --large agrega volumen.
        # La ruta nested prueba tambien la creacion del directorio de destino.
        # Aprobar: proceso exitoso y cabecera, longitud y datos exactos.
        for n in SMALL + ((65_537,) + LARGE if args.large else (65_537,)):
            path = root / "nested" / f"input_{n}.dat"
            result = run(n, path, "random", 123)
            assert result.returncode == 0, result.stderr
            check_file(path, n)
            print(f"[PASS] N={n}: cabecera, longitud y todos los float32", flush=True)
        # Comprueba modos especiales mas alla del primer bloque. Aprobar
        # exige que constant conserve 5.0 y edge mantenga su patron continuo.
        for mode in ("constant", "edge"):
            path = root / f"{mode}.dat"
            result = run(65_537, path, mode, 123)
            assert result.returncode == 0, result.stderr
            check_file(path, 65_537, mode)
            print(f"[PASS] modo {mode}: continuidad entre bloques", flush=True)
        # Destino preexistente: verifica que rechazar argumentos invalidos
        # no sobrescriba su contenido. No simula fallos durante una escritura.
        original = root / "protected.dat"
        original.write_bytes(b"no modificar")
        # Casos: N negativo, N fuera de int32, N no numerico, modo desconocido
        # y semilla no numerica. Aprobar exige error sin Traceback y bytes intactos.
        for invalid in ((-1, original), (2**31, original), ("abc", original),
                        (1, original, "invalid"), (1, original, "random", "bad_seed")):
            result = run(*invalid)
            assert result.returncode != 0 and "Traceback" not in result.stderr
            assert original.read_bytes() == b"no modificar"
        print("[PASS] entradas invalidas: error controlado, destino intacto", flush=True)
        # Interfaz por lote: exige exito y valida cada archivo esperado de
        # small, incluidos los modos constant y edge de N=16.
        result = run("--suite", "small", "--out-dir", root / "suite", "--seed", 123)
        assert result.returncode == 0, result.stderr
        for n in SMALL:
            check_file(root / "suite" / f"input_{n}.dat", n)
        for mode in ("constant", "edge"):
            check_file(root / "suite" / f"input_16_{mode}.dat", 16, mode)
        # Repetir la interfaz moderna produce exactamente los bytes de la antigua.
        # El lote anterior ya se contrasto con la secuencia de semilla 123;
        # ahora --seed debe producir el mismo archivo para N=16.
        repeated = root / "repeat.dat"
        assert run(16, repeated, "--seed", 123).returncode == 0
        assert repeated.read_bytes() == (root / "suite/input_16.dat").read_bytes()
        print("[PASS] lote pequeno y reproducibilidad entre interfaces", flush=True)
    # Solo se alcanza este mensaje si ninguna comprobacion produjo un fallo.
    print("ENTRADAS: TODAS LAS PRUEBAS PASAN")


if __name__ == "__main__":
    main()
