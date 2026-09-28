#!/usr/bin/env python3
"""Valida contadores de perf stat y publica tablas comparativas."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

EVENTS = ('cycles', 'instructions', 'cache-misses', 'cache-references')


def parse_counters(text):
    """Lee perf stat -x ';' con LC_ALL=C y eventos sin modificadores."""
    counters = {}
    for fields in csv.reader(text.splitlines(), delimiter=';'):
        if len(fields) < 3 or fields[0].lstrip().startswith('#'):
            continue
        event = fields[2].strip()
        if event not in EVENTS:
            continue
        if event in counters:
            raise ValueError(f'Evento duplicado: {event}')
        try:
            value = float(fields[0].strip())
        except ValueError as exc:
            raise ValueError(f'Evento no disponible: {event}: {fields[0]}') from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'Contador invalido: {event}')
        # Los campos 4 y 5, cuando existen, son tiempo activo y porcentaje activo.
        percent = fields[4].strip().rstrip('%') if len(fields) > 4 else ''
        if percent and (not math.isfinite(float(percent)) or not 0 < float(percent) <= 100):
            raise ValueError(f'Porcentaje activo invalido: {event}')
        counters[event] = (value, float(percent) if percent else None)
    missing = set(EVENTS) - counters.keys()
    if missing:
        raise ValueError(f'Faltan eventos: {", ".join(sorted(missing))}')
    if counters['cycles'][0] <= 0 or counters['instructions'][0] <= 0:
        raise ValueError('Ciclos e instrucciones deben ser mayores que cero')
    if counters['cache-misses'][0] > counters['cache-references'][0]:
        raise ValueError('Fallos de cache mayores que referencias; revise los eventos de la PMU')
    return counters


def analyze(directory):
    directory = Path(directory)
    if (directory / 'FAILED.txt').exists():
        raise ValueError('La ejecucion fallo; no se publican resultados parciales')
    metadata = json.loads((directory / 'metadata.json').read_text())
    sizes, runs, reps = metadata['sizes'], metadata['perf_runs'], metadata['reps']
    if metadata['mode'] != 'perf' or not sizes or len(set(sizes)) != len(sizes):
        raise ValueError('Metadatos incompatibles')
    if runs < 1 or reps < 1 or any(n < 1 for n in sizes):
        raise ValueError('Tamanos y repeticiones deben ser positivos')
    samples, summaries = [], []
    for n in sizes:
        for version in ('scalar', 'vector'):
            group = []
            for index in range(1, runs + 1):
                counters = parse_counters((directory / f'{version}_{n}_{index}.csv').read_text())
                c, ins, misses, refs = [counters[e][0] for e in EVENTS]
                active = [value[1] for value in counters.values() if value[1] is not None]
                minimum = min(active) if active else None
                row = [n, version, index, reps, c, ins, misses, refs,
                       ins / c, 100 * misses / refs if refs else '',
                       minimum if minimum is not None else '']
                samples.append(row)
                group.append(row)
            means = [statistics.mean(row[col] for row in group) for col in range(4, 8)]
            deviations = [statistics.stdev(row[col] for row in group) if runs > 1 else ''
                          for col in range(4, 8)]
            active = [row[10] for row in group if row[10] != '']
            summaries.append([n, version, runs, reps, *means, *deviations,
                              means[1] / means[0],
                              100 * means[2] / means[3] if means[3] else '',
                              min(active) if active else ''])
    # Validar todos los pares antes de escribir los resumenes.
    for name, header, rows in [
        ('perf_samples.csv', ['n', 'version', 'sample', 'kernel_reps', 'cycles',
         'instructions', 'cache_misses', 'cache_references', 'ipc',
         'cache_miss_percent', 'min_running_percent'], samples),
        ('perf_summary.csv', ['n', 'version', 'samples', 'kernel_reps', 'cycles_mean',
         'instructions_mean', 'cache_misses_mean', 'cache_references_mean',
         'cycles_std', 'instructions_std', 'cache_misses_std', 'cache_references_std',
         'ipc', 'cache_miss_percent', 'min_running_percent'], summaries),
    ]:
        with (directory / name).open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)
    lines = ['# Comparacion de contadores de hardware', '',
             'Alcance: proceso completo, incluida lectura, escritura, asignacion de memoria y driver.',
             'Los contadores no representan exclusivamente las funciones NASM.', '',
             'IPC = suma(instrucciones) / suma(ciclos).',
             'Fallos (%) = 100 * suma(cache-misses) / suma(cache-references).',
             'Los conteos son promedios por proceso; cada proceso repite el kernel segun kernel_reps.',
             'La desviacion estandar muestral se incluye en perf_summary.csv; con una muestra queda vacia.', '',
             '| N | Version | Muestras | Kernel reps | Ciclos | Instrucciones | IPC | Cache misses | Fallos (%) | Activo minimo (%) |',
             '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        rate = f'{r[13]:.4f}' if r[13] != '' else 'N/D'
        active = f'{r[14]:.2f}' if r[14] != '' else 'N/D'
        lines.append(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]:.2f} | {r[5]:.2f} | {r[12]:.4f} | {r[6]:.2f} | {rate} | {active} |')
    lines += ['', 'Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.',
              'Un denominador de referencias cero produce N/D, no una tasa de cero.',
              'El significado de cache-references/cache-misses depende de la CPU y su PMU;',
              'no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.',
              'Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.',
              'Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.', '']
    (directory / 'perf_report.md').write_text('\n'.join(lines), encoding='utf-8')
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        rows = analyze(args.directory)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Tabla lista: {args.directory / "perf_report.md"} ({len(rows)} filas)')


if __name__ == '__main__':
    main()
