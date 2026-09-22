#!/usr/bin/env python3
"""Valida el generador sin depender de kernels NASM ni de NumPy."""
import argparse
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile

GEN = Path(__file__).with_name("gen_input.py")
SMALL = (0, 1, 7, 8, 15, 16, 1000)
LARGE = (100_000, 1_000_000, 50_000_000)


def run(*args):
    return subprocess.run([sys.executable, str(GEN), *map(str, args)],
                          capture_output=True, text=True, timeout=180)


def check_file(path, n, mode="random"):
    assert path.stat().st_size == 4 + 4*n, f"Longitud incorrecta: {path}"
    rng = random.Random(123)
    edge = (-1e6, 1e6, 0.0, -0.0001, 0.0001, -1.0, 1.0)
    with path.open("rb") as stream:
        assert stream.read(4) == struct.pack("<i", n), "Cabecera incorrecta"
        # Bloques distintos al generador para comprobar continuidad entre bloques.
        for start in range(0, n, 100_003):
            count = min(100_003, n - start)
            if mode == "random":
                expected = [rng.uniform(-100, 100) for _ in range(count)]
            elif mode == "constant":
                expected = [5.0] * count
            else:
                expected = [edge[i % 7] for i in range(start, start + count)]
            assert stream.read(4*count) == struct.pack(f"<{count}f", *expected), f"Datos incorrectos: {path}, bloque {start}"
        assert stream.read(1) == b"", "Bytes sobrantes"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--large", action="store_true", help="incluye 50 millones de valores")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="input_test_") as temp:
        root = Path(temp)
        for n in SMALL + ((65_537,) + LARGE if args.large else (65_537,)):
            path = root / "nested" / f"input_{n}.dat"
            result = run(n, path, "random", 123)
            assert result.returncode == 0, result.stderr
            check_file(path, n)
            print(f"[PASS] N={n}: cabecera, longitud y todos los float32", flush=True)
        for mode in ("constant", "edge"):
            path = root / f"{mode}.dat"
            result = run(65_537, path, mode, 123)
            assert result.returncode == 0, result.stderr
            check_file(path, 65_537, mode)
            print(f"[PASS] modo {mode}: continuidad entre bloques", flush=True)
        original = root / "protected.dat"
        original.write_bytes(b"no modificar")
        for invalid in ((-1, original), (2**31, original), ("abc", original),
                        (1, original, "invalid"), (1, original, "random", "bad_seed")):
            result = run(*invalid)
            assert result.returncode != 0 and "Traceback" not in result.stderr
            assert original.read_bytes() == b"no modificar"
        print("[PASS] entradas invalidas: error controlado, destino intacto", flush=True)
        result = run("--suite", "small", "--out-dir", root / "suite", "--seed", 123)
        assert result.returncode == 0, result.stderr
        for n in SMALL:
            check_file(root / "suite" / f"input_{n}.dat", n)
        for mode in ("constant", "edge"):
            check_file(root / "suite" / f"input_16_{mode}.dat", 16, mode)
        # Repetir la interfaz moderna produce exactamente los bytes de la antigua.
        repeated = root / "repeat.dat"
        assert run(16, repeated, "--seed", 123).returncode == 0
        assert repeated.read_bytes() == (root / "suite/input_16.dat").read_bytes()
        print("[PASS] lote pequeno y reproducibilidad entre interfaces", flush=True)
    print("ENTRADAS: TODAS LAS PRUEBAS PASAN")


if __name__ == "__main__":
    main()
