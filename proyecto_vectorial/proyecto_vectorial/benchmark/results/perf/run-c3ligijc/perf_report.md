# Comparacion de contadores de hardware

Alcance: proceso completo, incluida lectura, escritura, asignacion de memoria y driver.
Los contadores no representan exclusivamente las funciones NASM.

IPC = suma(instrucciones) / suma(ciclos).
Fallos (%) = 100 * suma(cache-misses) / suma(cache-references).
Los conteos son promedios por proceso; cada proceso repite el kernel segun kernel_reps.
La desviacion estandar muestral se incluye en perf_summary.csv; con una muestra queda vacia.

| N | Version | Muestras | Kernel reps | Ciclos | Instrucciones | IPC | Cache misses | Fallos (%) | Activo minimo (%) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1000000 | scalar | 3 | 30 | 1750202559.67 | 1650224166.67 | 0.9429 | 4692027.67 | 18.7478 | 100.00 |
| 1000000 | vector | 3 | 30 | 238903098.00 | 176480693.33 | 0.7387 | 3009071.00 | 12.7929 | 100.00 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
