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

SMALL = (0, 1, 7, 8, 15, 16, 1000)
LARGE = (1000, 100_000, 1_000_000, 50_000_000)
EDGE = (-1e6, 1e6, 0.0, -0.0001, 0.0001, -1.0, 1.0)
BLOCK = 65_536
MAX_N = 2**31 - 1


def generate(n, destination, mode="random", seed=None):
    """Escribe atomicamente; conserva el archivo anterior si falla la generacion."""
    if not 0 <= n <= MAX_N:
        raise ValueError(f"N debe estar entre 0 y {MAX_N}")
    if mode not in ("random", "constant", "edge"):
        raise ValueError(f"Modo desconocido: {mode}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(struct.pack("<i", n))
            for start in range(0, n, BLOCK):
                count = min(BLOCK, n - start)
                if mode == "random":
                    values = [rng.uniform(-100.0, 100.0) for _ in range(count)]
                elif mode == "constant":
                    values = [5.0] * count
                else:
                    values = [EDGE[i % len(EDGE)] for i in range(start, start + count)]
                stream.write(struct.pack(f"<{count}f", *values))
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)
    print(f"Generado '{destination}' con N={n}, modo={mode}, bytes={4 + 4*n}")


def main():
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
        sizes = SMALL if args.suite == "small" else LARGE if args.suite == "large" else tuple(dict.fromkeys(SMALL + LARGE))
        seed = args.seed if args.seed is not None else 123
        jobs = [(n, args.out_dir / f"input_{n}.dat", "random") for n in sizes]
        if args.suite in ("small", "all"):
            jobs += [(16, args.out_dir / f"input_16_{mode}.dat", mode) for mode in ("constant", "edge")]
    else:
        if args.n is None or args.output is None:
            parser.error("indique N y salida.dat, o use --suite")
        if args.seed is not None and args.legacy_seed is not None:
            parser.error("indique la semilla una sola vez")
        seed = args.seed if args.seed is not None else args.legacy_seed
        jobs = [(args.n, args.output, args.mode)]
    try:
        for n, path, mode in jobs:
            generate(n, path, mode, seed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
