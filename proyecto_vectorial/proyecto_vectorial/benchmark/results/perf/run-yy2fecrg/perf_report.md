# Comparacion de contadores de hardware

Alcance: proceso completo, incluida lectura, escritura, asignacion de memoria y driver.
Los contadores no representan exclusivamente las funciones NASM.

IPC = suma(instrucciones) / suma(ciclos).
Fallos (%) = 100 * suma(cache-misses) / suma(cache-references).
Los conteos son promedios por proceso; cada proceso repite el kernel segun kernel_reps.
La desviacion estandar muestral se incluye en perf_summary.csv; con una muestra queda vacia.

| N | Version | Muestras | Kernel reps | Ciclos | Instrucciones | IPC | Cache misses | Fallos (%) | Activo minimo (%) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1000 | scalar | 3 | 30 | 1539361.67 | 2170743.67 | 1.4102 | 7391.67 | 31.1381 | 100.00 |
| 1000 | vector | 3 | 30 | 601682.33 | 435539.67 | 0.7239 | 6634.33 | 29.1602 | 100.00 |
| 100000 | scalar | 3 | 30 | 105618842.33 | 195222610.67 | 1.8484 | 98986.67 | 4.3346 | 100.00 |
| 100000 | vector | 3 | 30 | 14699750.00 | 20113607.33 | 1.3683 | 10413.33 | 0.4850 | 100.00 |
| 1000000 | scalar | 3 | 30 | 1052610244.00 | 1950224438.33 | 1.8528 | 3697727.00 | 14.6232 | 100.00 |
| 1000000 | vector | 3 | 30 | 169472362.67 | 198989687.00 | 1.1742 | 2780442.67 | 11.9457 | 100.00 |
| 50000000 | scalar | 3 | 30 | 55029550034.67 | 97500325061.67 | 1.7718 | 889678828.33 | 70.7803 | 100.00 |
| 50000000 | vector | 3 | 30 | 11735067233.00 | 9937837378.33 | 0.8468 | 722099727.33 | 66.0966 | 100.00 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
