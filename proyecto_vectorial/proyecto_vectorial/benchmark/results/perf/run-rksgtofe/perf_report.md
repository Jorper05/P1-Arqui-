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
| 1000 | scalar | 3 | 200000 | 6364961214.67 | 7562712810.00 | 1.1882 | 72364.67 | 7.3848 | 100.00 | 31.825 | 37.814 | 0.00036 |
| 1000 | vector | 3 | 200000 | 1383488515.00 | 1253911774.67 | 0.9063 | 37311.33 | 8.0502 | 100.00 | 6.917 | 6.270 | 0.00019 |
| 100000 | scalar | 3 | 2000 | 5464937061.33 | 7403599333.67 | 1.3547 | 669081.67 | 0.4494 | 100.00 | 27.325 | 37.018 | 0.00335 |
| 100000 | vector | 3 | 2000 | 564680267.67 | 1078759321.67 | 1.9104 | 95175.67 | 0.0724 | 100.00 | 2.823 | 5.394 | 0.00048 |
| 1000000 | scalar | 3 | 200 | 5671166239.67 | 7417438528.33 | 1.3079 | 23274957.33 | 14.3551 | 100.00 | 28.356 | 37.087 | 0.11637 |
| 1000000 | vector | 3 | 200 | 695471276.67 | 1092453844.67 | 1.5708 | 11895425.33 | 8.0167 | 100.00 | 3.477 | 5.462 | 0.05948 |
| 50000000 | scalar | 3 | 30 | 45995611906.00 | 56350417894.67 | 1.2251 | 894344556.00 | 71.3139 | 100.00 | 30.664 | 37.567 | 0.59623 |
| 50000000 | vector | 3 | 30 | 9469820894.00 | 8912910658.67 | 0.9412 | 663774765.00 | 62.1462 | 100.00 | 6.313 | 5.942 | 0.44252 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
