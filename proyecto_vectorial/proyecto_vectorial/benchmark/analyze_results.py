#!/usr/bin/env python3
"""Resume muestras de kernel (ms y ciclos TSC) y dibuja speedup con eje N logaritmico."""
import argparse
import csv
import math
from pathlib import Path
import statistics
import sys

THEORETICAL_SPEEDUP = 8  # AVX2: 8 floats de 32 bits por instruccion
SUPERSCRIPT = str.maketrans('0123456789', '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079')


def read_samples(directory):
    """Devuelve ({(n, version): {muestra: (ms, ciclos|None)}}, hay_ciclos)."""
    groups = {}
    with (directory / 'samples.csv').open(newline='') as stream:
        reader = csv.DictReader(stream)
        has_cycles = 'kernel_cycles' in (reader.fieldnames or [])
        for row in reader:
            n, index, elapsed = int(row['n']), int(row['sample']), float(row['kernel_ms'])
            cycles = float(row['kernel_cycles']) if has_cycles else None
            version = row['version']
            if (n <= 0 or index <= 0 or version not in ('scalar', 'vector')
                    or not math.isfinite(elapsed) or elapsed <= 0
                    or (has_cycles and (not math.isfinite(cycles) or cycles <= 0))):
                raise ValueError('Muestra invalida')
            samples = groups.setdefault((n, version), {})
            if index in samples:
                raise ValueError('Muestra duplicada')
            samples[index] = (elapsed, cycles)
    if not groups:
        raise ValueError('No hay muestras')
    return groups, has_cycles


def mean_std(values):
    values = list(values)
    return statistics.mean(values), statistics.stdev(values)


def tick_label(exponent):
    return '10' + str(exponent).translate(SUPERSCRIPT)


def write_svg(path, xs, ys):
    """Grafico de speedup sin dependencias (se usa si falta matplotlib)."""
    width, height, left, right, top, bottom = 800, 450, 70, 30, 50, 60
    # Margen de un cuarto de decada para que los extremos no queden sobre el marco.
    low = math.log10(min(xs)) - 0.25
    high = math.log10(max(xs)) + 0.25
    ymax = max(THEORETICAL_SPEEDUP, max(ys)) * 1.1

    def px(x):
        return left + (math.log10(x) - low) / (high - low) * (width - left - right)

    def py(y):
        return height - bottom - y / ymax * (height - top - bottom)

    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="13">',
           f'<rect width="{width}" height="{height}" fill="white"/>',
           f'<text x="{width / 2}" y="28" text-anchor="middle" font-size="17">'
           'Rendimiento del normalizador estadistico</text>']
    for k in range(math.ceil(low), math.floor(high) + 1):
        x = px(10 ** k)
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - bottom}" stroke="#ddd"/>')
        out.append(f'<text x="{x:.1f}" y="{height - bottom + 20}" text-anchor="middle">{tick_label(k)}</text>')
    for value in range(0, int(ymax) + 1):
        y = py(value)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{value}</text>')
    out.append(f'<rect x="{left}" y="{top}" width="{width - left - right}" height="{height - top - bottom}" '
               'fill="none" stroke="black"/>')
    for value, color, label in ((1, 'gray', 'Igual rendimiento (1x)'),
                                (THEORETICAL_SPEEDUP, '#c0392b', 'Referencia de 8×')):
        y = py(value)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{color}" '
                   'stroke-dasharray="6 4" stroke-width="1.5"/>')
        out.append(f'<text x="{width - right - 6}" y="{y - 5:.1f}" text-anchor="end" fill="{color}">{label}</text>')
    points = ' '.join(f'{px(x):.1f},{py(y):.1f}' for x, y in zip(xs, ys))
    out.append(f'<polyline points="{points}" fill="none" stroke="#1f77b4" stroke-width="2"/>')
    for x, y in zip(xs, ys):
        out.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="4.5" fill="#1f77b4"/>')
        out.append(f'<text x="{px(x):.1f}" y="{py(y) - 10:.1f}" text-anchor="middle">{y:.2f}x</text>')
    out.append(f'<text x="{(left + width - right) / 2}" y="{height - 15}" text-anchor="middle">'
               'N (elementos, escala logaritmica)</text>')
    out.append(f'<text transform="translate(20 {(top + height - bottom) / 2}) rotate(-90)" '
               'text-anchor="middle">Speedup = t_escalar / t_AVX2</text>')
    out.append('</svg>')
    Path(path).write_text('\n'.join(out) + '\n', encoding='utf-8')


def plot(directory, xs, ys):
    """PNG con matplotlib si existe; si no, SVG sin dependencias. Devuelve el archivo."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Aviso: matplotlib no esta instalado; se genera speedup.svg sin dependencias. '
              'Para el PNG: pip install matplotlib y repita el analisis.', file=sys.stderr)
        write_svg(directory / 'speedup.svg', xs, ys)
        return directory / 'speedup.svg'
    fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
    ax.plot(xs, ys, 'o-', label='Escalar / AVX2')
    for x, y in zip(xs, ys):
        ax.annotate(f'{y:.2f}x', (x, y), textcoords='offset points', xytext=(0, 8), ha='center')
    ax.axhline(1, color='gray', linestyle='--', label='Igual rendimiento (1x)')
    ax.axhline(THEORETICAL_SPEEDUP, color='#c0392b', linestyle='--', label='Referencia de 8×')
    ax.set(xscale='log', xlabel='N (elementos, escala logaritmica)', ylabel='Speedup',
           title='Rendimiento del normalizador estadistico')
    ax.set_ylim(bottom=0, top=max(THEORETICAL_SPEEDUP, max(ys)) * 1.1)
    ax.grid(True, alpha=.25)
    ax.legend()
    fig.savefig(directory / 'speedup.png', dpi=180)
    plt.close(fig)
    return directory / 'speedup.png'


def analyze(directory):
    directory = Path(directory)
    if (directory / 'FAILED.txt').exists():
        raise ValueError('La ejecucion fallo; no se pueden publicar sus resultados parciales')
    groups, has_cycles = read_samples(directory)
    rows, cycle_rows, individual = [], [], {'scalar': [], 'vector': []}
    for n in sorted({key[0] for key in groups}):
        pair = [groups.get((n, v), {}) for v in individual]
        count = len(pair[0])
        if count < 2 or any(set(p) != set(range(1, count + 1)) for p in pair):
            raise ValueError(f'N={n}: faltan muestras pareadas y consecutivas')
        summary, cycles_summary = [], []
        for version, samples in zip(individual, pair):
            avg, std = mean_std(s[0] for s in samples.values())
            summary.extend((avg, std))
            entry = [n, count, avg, std]
            if has_cycles:
                c_avg, c_std = mean_std(s[1] for s in samples.values())
                cycles_summary.extend((c_avg, c_std))
                entry += [c_avg, c_std]
            individual[version].append(entry)
        rows.append([n, count, *summary, summary[0] / summary[2]])
        if has_cycles:
            cycle_rows.append([*cycles_summary, cycles_summary[0] / cycles_summary[2]])
    # Todo se valido; ahora se publican tablas y grafico.
    for version, values in individual.items():
        with (directory / f'{version}.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['n', 'samples', 'mean_ms', 'std_ms'] +
                            (['mean_cycles', 'std_cycles'] if has_cycles else []))
            writer.writerows(values)
    with (directory / 'summary.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['n', 'samples', 'scalar_mean_ms', 'scalar_std_ms', 'vector_mean_ms',
                         'vector_std_ms', 'speedup'] +
                        (['scalar_mean_cycles', 'scalar_std_cycles', 'vector_mean_cycles',
                          'vector_std_cycles', 'speedup_cycles'] if has_cycles else []))
        writer.writerows(row + (cycle_rows[i] if has_cycles else []) for i, row in enumerate(rows))
    plot(directory, [r[0] for r in rows], [r[-1] for r in rows])
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
