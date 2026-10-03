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
| 1000 | scalar | 3 | 200000 | 6347607803.00 | 7562714718.00 | 1.1914 | 24209.00 | 2.5897 | 100.00 | 31.738 | 37.814 | 0.00012 |
| 1000 | vector | 3 | 200000 | 1371415341.00 | 1251508114.00 | 0.9126 | 16936.67 | 3.6023 | 100.00 | 6.857 | 6.258 | 0.00008 |
| 100000 | scalar | 3 | 2000 | 5402285399.33 | 7403598008.00 | 1.3705 | 284549.33 | 0.1938 | 100.00 | 27.011 | 37.018 | 0.00142 |
| 100000 | vector | 3 | 2000 | 557486561.00 | 1078735474.67 | 1.9350 | 73396.67 | 0.0531 | 100.00 | 2.787 | 5.394 | 0.00037 |
| 1000000 | scalar | 3 | 200 | 5700998487.33 | 7417438202.33 | 1.3011 | 27545768.00 | 16.6554 | 100.00 | 28.505 | 37.087 | 0.13773 |
| 1000000 | vector | 3 | 200 | 722434636.00 | 1092451397.33 | 1.5122 | 15044414.33 | 9.9864 | 100.00 | 3.612 | 5.462 | 0.07522 |
| 50000000 | scalar | 3 | 30 | 45186254855.00 | 56350414331.33 | 1.2471 | 894467067.67 | 70.6833 | 100.00 | 30.124 | 37.567 | 0.59631 |
| 50000000 | vector | 3 | 30 | 8731566724.33 | 8912905990.67 | 1.0208 | 650896103.00 | 60.5599 | 100.00 | 5.821 | 5.942 | 0.43393 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
