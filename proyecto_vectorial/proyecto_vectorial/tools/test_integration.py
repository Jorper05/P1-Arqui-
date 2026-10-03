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
    # Semilla fija: reproduce el conjunto de datos en el mismo entorno NumPy.
    rng = np.random.default_rng(123)
    # Todos los remanentes posibles, ademas de los tamanos requeridos.
    # 0..17 cubre arreglos vacios, cortos y fronteras de ocho elementos.
    # Los tamanos adicionales comprueban varios bloques y sus remanentes.
    for n in sorted(set(range(18)) | {23, 24, 31, 32, 33, 1000}):
        yield f'random_{n}', rng.uniform(-100, 100, n).astype(np.float32)
    # Solo negativos: detecta, por ejemplo, extremos inicializados a cero.
    yield 'negative', -np.arange(1, 18, dtype=np.float32)
    # Suma/media cero: comprueba cancelacion y tolerancia absoluta para ceros.
    yield 'zero_sum', np.arange(-4, 5, dtype=np.float32)
    # Constantes en tamanos con y sin remanente: varianza y sigma cero.
    # Normalizar con sigma cero debe copiar la entrada, sin dividir por cero.
    for n in (1, 7, 8, 15, 16, 17):
        yield f'constant_{n}', np.full(n, 3.5, dtype=np.float32)
    # Caso totalmente nulo: estadisticos y normalizacion deben ser cero.
    yield 'zeros', np.zeros(16, dtype=np.float32)
    # Magnitudes grandes cuyo cuadrado todavia cabe en float32.
    yield 'extreme', np.array([-1e10, 1e10, -1e9, 1e9, -3, 4, 0, 2, -2], dtype=np.float32)
    # Extremos en el ultimo elemento: detecta omisiones al recorrer o reducir.
    # N=16 es multiplo de ocho: estos dos casos no prueban un remanente escalar.
    yield 'tail_min', np.array([1] * 15 + [-100], dtype=np.float32)
    yield 'tail_max', np.array([-1] * 15 + [100], dtype=np.float32)


def execute(binary, mode, path, parameters):
    # El ejecutable auxiliar llama al kernel de stats o normalize por separado.
    # Aprobar requiere terminar con codigo cero y resultados numericos legibles.
    result = subprocess.run([str(binary), mode, str(path), *parameters],
                            capture_output=True, text=True, timeout=15)
    if result.returncode == 77:
        # Falta de AVX2 no se considera una validacion completa ni un PASS.
        raise ValueError('AVX2 no disponible; validacion incompleta')
    if result.returncode:
        raise ValueError(f'codigo={result.returncode}: {result.stderr.strip()}')
    return np.array([float(value) for value in result.stdout.split()], dtype=np.float64)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # Permite aislar una etapa para localizar fallos, o ejecutar todas.
    parser.add_argument('--stage', choices=('all', 'scalar-stats', 'scalar-normalize',
                                           'vector-stats', 'vector-normalize', 'driver'), default='all')
    args = parser.parse_args()
    failures = checks = 0
    stages = [('scalar-stats', 'scalar', 'stats'),
              ('scalar-normalize', 'scalar', 'normalize'),
              ('vector-stats', 'vector', 'stats'),
              ('vector-normalize', 'vector', 'normalize')]
    # Conserva resultados escalares para compararlos con AVX2 cuando ambas
    # etapas se ejecutan. Una etapa vectorial aislada solo compara con referencia.
    cache = {}
    with tempfile.TemporaryDirectory(prefix='integration-') as directory:
        inputs = []
        for name, values in cases():
            path = Path(directory) / f'{name}.dat'
            # Archivos binarios de prueba: int32 N y N float32 little endian.
            path.write_bytes(struct.pack('<i', len(values)) + values.astype('<f4').tobytes())
            inputs.append((name, values, path))
        for stage, version, mode in stages:
            if args.stage not in ('all', stage):
                continue
            print(f'\n{stage}', flush=True)
            for name, values, path in inputs:
                if len(values):
                    # Usa la referencia NumPy/math.fsum definida por el verificador.
                    ref, _ = reference_stats(values)
                else:
                    # Kernel aislado con N=0: stats debe escribir cuatro ceros;
                    # normalize debe devolver una salida vacia sin acceder a datos.
                    # Este contrato difiere del driver, que rechaza la entrada vacia.
                    ref = dict(mean=0, var=0, min=0, max=0, stddev=0)
                # stats: compara las cuatro salidas, en el orden del auxiliar.
                jobs = [('stats', [], np.array([ref[k] for k in ('mean', 'var', 'min', 'max')]))]
                if mode == 'normalize':
                    jobs = []
                    # Parametros de NumPy: no depende de compute_stats NASM.
                    # reference: normalizacion con estadisticos de referencia.
                    # explicit: media/sigma conocidos, distintos de los datos,
                    # para comprobar que el kernel usa los argumentos recibidos.
                    # zero_sigma: copia exacta esperada incluso con media=7.
                    for label, mean, sigma in (('reference', ref['mean'], ref['stddev']),
                                               ('explicit', np.float32(1.25), np.float32(2.5)),
                                               ('zero_sigma', np.float32(7), np.float32(0))):
                        expected = values.copy() if sigma == 0 else (values - mean) / sigma
                        # Nueve cifras significativas permiten transportar float32
                        # por argumentos de texto sin perder su representacion.
                        jobs.append((label, [format(float(mean), '.9g'), format(float(sigma), '.9g')], expected))
                for label, parameters, expected in jobs:
                    checks += 1
                    key = (mode, name, label)
                    try:
                        actual = execute(ROOT / f'bin/test_kernels_{version}', mode, path, parameters)
                        # Aprobar exige formas iguales, valores finitos y TODOS los
                        # elementos dentro de tolerancia: relativa 1e-4 para una
                        # referencia no nula; absoluta 1e-6 solo para referencia cero.
                        # Tambien zero_sigma se evalua con esta tolerancia, no con
                        # igualdad exacta. actual[:4] solo limita el diagnostico.
                        if not close(actual, expected, 1e-4, 1e-6):
                            raise ValueError(f'difiere de NumPy: obtenido={actual[:4]}, esperado={expected[:4]}')
                        # Con la etapa escalar disponible, AVX2 debe cumplir tambien
                        # las mismas tolerancias frente al resultado escalar completo.
                        if version == 'vector' and key in cache and not close(actual, cache[key], 1e-4, 1e-6):
                            raise ValueError('difiere del resultado escalar')
                        if version == 'scalar':
                            cache[key] = actual
                        print(f'[PASS] {name}/{label}')
                    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                        # Cuenta el fallo y continua para mostrar los demas casos.
                        failures += 1
                        print(f'[FAIL] {name}/{label}: {exc}')
        if args.stage in ('all', 'driver'):
            print('\nIntegracion con driver y archivos', flush=True)
            for name, values, path in inputs:
                checks += 1
                try:
                    # run_case ejecuta ambos drivers y valida archivos, estadisticos,
                    # arreglo normalizado completo y formula con parametros propios.
                    # Para N=0 exige rechazo controlado sin crear archivos de salida.
                    # Aprobar requiere que todas sus comprobaciones devuelvan True.
                    if not run_case(path, ROOT / 'bin/norm_scalar', ROOT / 'bin/norm_vector', 1e-4, 1e-6):
                        failures += 1
                except (OSError, ValueError, FloatingPointError, subprocess.TimeoutExpired) as exc:
                    failures += 1
                    print(f'[FAIL] {name}: {exc}')
    # Resultado de las etapas seleccionadas: codigo cero solo si no hubo fallos.
    # Para verificar el conjunto completo, usar --stage all (valor predeterminado).
    print(f'\nRESULTADO: {"PASA" if not failures else "FALLA"}; comprobaciones={checks}; fallos={failures}')
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
