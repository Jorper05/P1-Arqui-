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
| 1000 | scalar | 3 | 200000 | 5591045327.33 | 7552095366.67 | 1.3507 | 71761.33 | 1.7081 | 100.00 | 27.955 | 37.760 | 0.00036 |
| 1000 | vector | 3 | 200000 | 1607980803.33 | 1240892786.33 | 0.7717 | 86825.67 | 2.4250 | 100.00 | 8.040 | 6.204 | 0.00043 |
| 100000 | scalar | 3 | 2000 | 4354617705.67 | 7403321727.00 | 1.7001 | 1857521.33 | 1.4737 | 100.00 | 21.773 | 37.017 | 0.00929 |
| 100000 | vector | 3 | 2000 | 384192314.00 | 1078458082.67 | 2.8071 | 2135096.00 | 1.8012 | 100.00 | 1.921 | 5.392 | 0.01068 |
| 1000000 | scalar | 3 | 200 | 4341731977.00 | 7415851320.67 | 1.7080 | 1490490.67 | 0.9795 | 100.00 | 21.709 | 37.079 | 0.00745 |
| 1000000 | vector | 3 | 200 | 377864571.00 | 1090863714.33 | 2.8869 | 1524825.00 | 1.0040 | 100.00 | 1.889 | 5.454 | 0.00762 |
| 50000000 | scalar | 3 | 30 | 33301169224.00 | 56272316874.67 | 1.6898 | 12117192.67 | 1.0425 | 100.00 | 22.201 | 37.515 | 0.00808 |
| 50000000 | vector | 3 | 30 | 7707698746.67 | 8834764562.33 | 1.1462 | 28217189.00 | 2.4482 | 100.00 | 5.138 | 5.890 | 0.01881 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
