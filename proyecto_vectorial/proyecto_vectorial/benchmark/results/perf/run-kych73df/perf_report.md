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
| 1000 | scalar | 3 | 200000 | 7164775356.67 | 13063087797.00 | 1.8232 | 35892.67 | 4.3925 | 100.00 | 35.824 | 65.315 | 0.00018 |
| 1000 | vector | 3 | 200000 | 1000403421.67 | 1493246959.67 | 1.4926 | 10171.00 | 9.2621 | 100.00 | 5.002 | 7.466 | 0.00005 |
| 100000 | scalar | 3 | 2000 | 7062568507.00 | 13007345895.67 | 1.8417 | 286968.67 | 0.1888 | 100.00 | 35.313 | 65.037 | 0.00143 |
| 100000 | vector | 3 | 2000 | 917421669.33 | 1327559696.00 | 1.4471 | 26870.00 | 0.0197 | 100.00 | 4.587 | 6.638 | 0.00013 |
| 1000000 | scalar | 3 | 200 | 7182699687.33 | 13065283111.67 | 1.8190 | 24085963.00 | 14.3146 | 100.00 | 35.913 | 65.326 | 0.12043 |
| 1000000 | vector | 3 | 200 | 1055506845.33 | 1332011392.67 | 1.2620 | 12006505.67 | 7.7722 | 100.00 | 5.278 | 6.660 | 0.06003 |
| 50000000 | scalar | 3 | 30 | 57890362241.00 | 100750336201.33 | 1.7404 | 919600944.33 | 70.8338 | 100.00 | 38.594 | 67.167 | 0.61307 |
| 50000000 | vector | 3 | 30 | 11480074151.67 | 10269092920.00 | 0.8945 | 734346256.67 | 65.3783 | 100.00 | 7.653 | 6.846 | 0.48956 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
