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
| 1000 | scalar | 3 | 200000 | 5593378413.33 | 7552094570.33 | 1.3502 | 95655.00 | 2.8686 | 100.00 | 27.967 | 37.760 | 0.00048 |
| 1000 | vector | 3 | 200000 | 1611179755.00 | 1240898393.33 | 0.7702 | 81769.33 | 2.6764 | 100.00 | 8.056 | 6.204 | 0.00041 |
| 100000 | scalar | 3 | 2000 | 4352946829.00 | 7403321781.00 | 1.7008 | 1775402.67 | 1.4273 | 100.00 | 21.765 | 37.017 | 0.00888 |
| 100000 | vector | 3 | 2000 | 381630703.00 | 1078458255.00 | 2.8259 | 2176421.00 | 1.8082 | 100.00 | 1.908 | 5.392 | 0.01088 |
| 1000000 | scalar | 3 | 200 | 4353058678.00 | 7415851541.33 | 1.7036 | 1539408.00 | 1.0125 | 100.00 | 21.765 | 37.079 | 0.00770 |
| 1000000 | vector | 3 | 200 | 387816992.33 | 1090863770.67 | 2.8128 | 1501040.33 | 0.9879 | 100.00 | 1.939 | 5.454 | 0.00751 |
| 50000000 | scalar | 3 | 30 | 33170434767.67 | 56272279417.33 | 1.6965 | 11535056.67 | 0.9933 | 100.00 | 22.114 | 37.515 | 0.00769 |
| 50000000 | vector | 3 | 30 | 7367140921.00 | 8834768795.67 | 1.1992 | 24099633.33 | 2.0849 | 100.00 | 4.911 | 5.890 | 0.01607 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
