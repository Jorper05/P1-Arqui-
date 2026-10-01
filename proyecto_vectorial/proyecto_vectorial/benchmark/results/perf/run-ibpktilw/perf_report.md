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
| 1000 | scalar | 3 | 200000 | 7766204393.00 | 13170918499.33 | 1.6959 | 236283.67 | 6.1067 | 100.00 | 38.831 | 65.855 | 0.00118 |
| 1000 | vector | 3 | 200000 | 1838507631.33 | 1601110740.33 | 0.8709 | 182056.33 | 7.5855 | 100.00 | 9.193 | 8.006 | 0.00091 |
| 100000 | scalar | 3 | 2000 | 6888625950.33 | 13003683418.33 | 1.8877 | 382375.67 | 0.2541 | 100.00 | 34.443 | 65.018 | 0.00191 |
| 100000 | vector | 3 | 2000 | 937113570.33 | 1329734122.67 | 1.4190 | 116501.67 | 0.0849 | 100.00 | 4.686 | 6.649 | 0.00058 |
| 1000000 | scalar | 3 | 200 | 7071380873.00 | 13017450208.67 | 1.8409 | 35088286.00 | 21.1456 | 100.00 | 35.357 | 65.087 | 0.17544 |
| 1000000 | vector | 3 | 200 | 1099306345.33 | 1342553602.67 | 1.2213 | 15245830.33 | 9.9435 | 100.00 | 5.497 | 6.713 | 0.07623 |
| 50000000 | scalar | 3 | 30 | 55609088821.00 | 98350424636.00 | 1.7686 | 900142975.33 | 70.8529 | 100.00 | 37.073 | 65.567 | 0.60010 |
| 50000000 | vector | 3 | 30 | 11225887506.00 | 10787924923.00 | 0.9610 | 720385400.67 | 65.2398 | 100.00 | 7.484 | 7.192 | 0.48026 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
