# Comparacion de contadores de hardware

Alcance: proceso completo, incluida lectura, escritura, asignacion de memoria y driver.
Los contadores no representan exclusivamente las funciones NASM; para que el kernel
domine, cada proceso repite el kernel (columna Kernel reps, escalada segun N).

IPC = suma(instrucciones) / suma(ciclos).
Fallos (%) = 100 * suma(cache-misses) / suma(cache-references).
Los conteos son promedios por proceso; cada proceso repite el kernel segun kernel_reps.
La desviacion estandar muestral se incluye en perf_summary.csv; con una muestra queda vacia.
Por elemento = contador / (N * Kernel reps): una llamada al kernel completo procesa N elementos.

| N | Version | Muestras | Kernel reps | Ciclos | Instrucciones | IPC | Cache misses | Fallos (%) | Activo minimo (%) | Ciclos/elem | Instr/elem | Misses/elem |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1000 | scalar | 3 | 200000 | 7622993659.67 | 13162913135.00 | 1.7267 | 35569.67 | 2.4118 | 100.00 | 38.115 | 65.815 | 0.00018 |
| 1000 | vector | 3 | 200000 | 1371650797.00 | 1253911252.67 | 0.9142 | 13894.67 | 2.7107 | 100.00 | 6.858 | 6.270 | 0.00007 |
| 100000 | scalar | 3 | 2000 | 6890873265.67 | 13003600991.33 | 1.8871 | 393518.33 | 0.2596 | 100.00 | 34.454 | 65.018 | 0.00197 |
| 100000 | vector | 3 | 2000 | 557142120.00 | 1078758994.67 | 1.9362 | 73132.67 | 0.0549 | 100.00 | 2.786 | 5.394 | 0.00037 |
| 1000000 | scalar | 3 | 200 | 7011440471.67 | 13017439517.00 | 1.8566 | 25177880.67 | 15.2831 | 100.00 | 35.057 | 65.087 | 0.12589 |
| 1000000 | vector | 3 | 200 | 668709096.00 | 1092454024.33 | 1.6337 | 11095355.67 | 7.4191 | 100.00 | 3.344 | 5.462 | 0.05548 |
| 50000000 | scalar | 3 | 30 | 55426820013.00 | 98350417453.67 | 1.7744 | 900086054.67 | 70.8880 | 100.00 | 36.951 | 65.567 | 0.60006 |
| 50000000 | vector | 3 | 30 | 8673850643.00 | 8912906590.67 | 1.0276 | 647864887.67 | 60.3163 | 100.00 | 5.783 | 5.942 | 0.43191 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
