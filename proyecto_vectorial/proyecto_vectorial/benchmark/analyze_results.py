#!/usr/bin/env python3
"""Resume muestras de kernel y dibuja speedup con eje N logaritmico."""
import argparse
import csv
import math
from pathlib import Path
import statistics


def analyze(directory):
    if (directory / 'FAILED.txt').exists():
        raise ValueError('La ejecucion fallo; no se pueden publicar sus resultados parciales')
    groups = {}
    with (directory / 'samples.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            n, index, elapsed = int(row['n']), int(row['sample']), float(row['kernel_ms'])
            version = row['version']
            if n <= 0 or index <= 0 or version not in ('scalar', 'vector') or not math.isfinite(elapsed) or elapsed <= 0:
                raise ValueError('Muestra invalida')
            samples = groups.setdefault((n, version), {})
            if index in samples:
                raise ValueError('Muestra duplicada')
            samples[index] = elapsed
    if not groups:
        raise ValueError('No hay muestras')
    rows, individual = [], {'scalar': [], 'vector': []}
    for n in sorted({key[0] for key in groups}):
        pair = [groups.get((n, v), {}) for v in individual]
        count = len(pair[0])
        if count < 2 or any(set(p) != set(range(1, count + 1)) for p in pair):
            raise ValueError(f'N={n}: faltan muestras pareadas y consecutivas')
        summary = []
        for version, samples in zip(individual, pair):
            avg, std = statistics.mean(samples.values()), statistics.stdev(samples.values())
            summary.extend((avg, std))
            individual[version].append([n, count, avg, std])
        rows.append([n, count, *summary, summary[0] / summary[2]])
    # Validar todo antes de publicar tablas.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for version, values in individual.items():
        with (directory / f'{version}.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['n', 'samples', 'mean_ms', 'std_ms'])
            writer.writerows(values)
    with (directory / 'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'samples', 'scalar_mean_ms', 'scalar_std_ms', 'vector_mean_ms', 'vector_std_ms', 'speedup'])
        writer.writerows(rows)
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    ax.plot([r[0] for r in rows], [r[-1] for r in rows], 'o-', label='Escalar / AVX2')
    ax.axhline(1, color='gray', linestyle='--', label='Igual rendimiento')
    ax.set(xscale='log', xlabel='N (elementos, escala logaritmica)', ylabel='Speedup',
           title='Rendimiento del normalizador estadistico')
    ax.grid(True, alpha=.25)
    ax.legend()
    fig.savefig(directory / 'speedup.png', dpi=180)
    plt.close(fig)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        rows = analyze(args.directory)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f'Analizados {len(rows)} tamanos en {args.directory}')


if __name__ == '__main__':
    main()
