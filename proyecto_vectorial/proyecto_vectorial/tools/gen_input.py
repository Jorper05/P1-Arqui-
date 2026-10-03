#!/usr/bin/env python3
"""Entradas little endian: int32 N seguido de N float32.

Compatible: gen_input.py N salida.dat [random|constant|edge] [semilla]
Lote: gen_input.py --suite small|large|all --out-dir data/inputs --seed 123
La escritura por bloques limita la memoria incluso para N=50_000_000.
"""
import argparse
import os
from pathlib import Path
import random
import struct
import tempfile

# Casos pequenos: arreglo vacio, un elemento, limites de bloques AVX de
# ocho floats y remanentes escalares; 1000 permite un caso mas amplio.
# N=0 genera una entrada para comprobar el rechazo de driver.c.
SMALL = (0, 1, 7, 8, 15, 16, 1000)
# Casos grandes para evaluar escalabilidad y rendimiento.
LARGE = (1000, 100_000, 1_000_000, 50_000_000)
# Patron de valores con signos, ceros y magnitudes distintas.
# Es un caso numerico exigente; no contiene NaN ni infinitos.
EDGE = (-1e6, 1e6, 0.0, -0.0001, 0.0001, -1.0, 1.0)
# Numero maximo de elementos construidos y empaquetados por bloque.
BLOCK = 65_536
# La cabecera usa un entero de 32 bits con signo: N no supera INT32_MAX.
MAX_N = 2**31 - 1


def generate(n, destination, mode="random", seed=None, random_limit=100.0):
    """Escribe atomicamente; conserva el archivo anterior si falla la generacion."""
    # Se admite N=0 para generar tambien el caso de entrada vacia.
    if not 0 <= n <= MAX_N:
        raise ValueError(f"N debe estar entre 0 y {MAX_N}")
    if mode not in ("random", "constant", "edge"):
        raise ValueError(f"Modo desconocido: {mode}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Generador local: no altera el estado aleatorio global. Una semilla
    # fija reproduce la secuencia en el mismo entorno; None usa la
    # inicializacion automatica de Python. constant y edge no usan el RNG.
    rng = random.Random(seed)
    temporary = None
    try:
        # El temporal se crea en el mismo directorio para que os.replace
        # publique el archivo completo mediante una sustitucion atomica.
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = stream.name
            # '<' fija little endian y 'i' guarda N como int32 de 4 bytes.
            stream.write(struct.pack("<i", n))
            # Solo se mantiene un bloque en memoria, incluso para N grande.
            for start in range(0, n, BLOCK):
                count = min(BLOCK, n - start)
                if mode == "random":
                    # Valores uniformes entre -random_limit y random_limit.
                    values = [rng.uniform(-random_limit, random_limit) for _ in range(count)]
                elif mode == "constant":
                    # Todos iguales: caso de varianza y desviacion cero.
                    values = [5.0] * count
                else:
                    # Repite EDGE sin reiniciar el patron entre bloques.
                    values = [EDGE[i % len(EDGE)] for i in range(start, start + count)]
                # Los valores son float de Python; 'f' los convierte a
                # float32 de 4 bytes, con el redondeo de esa representacion.
                # El archivo no incluye separadores ni relleno de alineacion.
                stream.write(struct.pack(f"<{count}f", *values))
        os.replace(temporary, destination)
        temporary = None
    finally:
        # Si la generacion falla, elimina el temporal pendiente.
        if temporary is not None:
            os.unlink(temporary)
    # Tamano exacto: 4 bytes de cabecera y 4 bytes por elemento.
    print(f"Generado '{destination}' con N={n}, modo={mode}, bytes={4 + 4*n}")


def main():
    # Conserva la interfaz posicional y permite generar lotes con --suite.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int, nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("mode", choices=("random", "constant", "edge"), nargs="?", default="random")
    parser.add_argument("legacy_seed", type=int, nargs="?")
    parser.add_argument("--suite", choices=("small", "large", "all"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/inputs"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.suite:
        if args.n is not None or args.output is not None:
            parser.error("--suite no admite argumentos posicionales")
        # all combina ambos conjuntos sin repetir N=1000.
        sizes = SMALL if args.suite == "small" else LARGE if args.suite == "large" else tuple(dict.fromkeys(SMALL + LARGE))
        # Los lotes usan 123 por defecto para facilitar su reproduccion.
        seed = args.seed if args.seed is not None else 123
        jobs = [(n, args.out_dir / f"input_{n}.dat", "random") for n in sizes]
        if args.suite in ("small", "all"):
            # Ademas de los aleatorios, genera dos casos especiales de N=16.
            jobs += [(16, args.out_dir / f"input_16_{mode}.dat", mode) for mode in ("constant", "edge")]
    else:
        if args.n is None or args.output is None:
            parser.error("indique N y salida.dat, o use --suite")
        if args.seed is not None and args.legacy_seed is not None:
            parser.error("indique la semilla una sola vez")
        # Un archivo admite semilla posicional o --seed. Si se omite,
        # seed queda en None y los datos aleatorios pueden variar por ejecucion.
        seed = args.seed if args.seed is not None else args.legacy_seed
        jobs = [(args.n, args.output, args.mode)]
    try:
        for n, path, mode in jobs:
            # Cada archivo reinicia su RNG con la misma semilla. En modo
            # random, los archivos pequenos comparten el prefijo de datos
            # con los grandes cuando se usa una semilla fija.
            generate(n, path, mode, seed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
