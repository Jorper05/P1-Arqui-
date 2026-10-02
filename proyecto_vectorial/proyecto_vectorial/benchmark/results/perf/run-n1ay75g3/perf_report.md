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
| 1000 | scalar | 3 | 200000 | 6352231104.00 | 7562713108.00 | 1.1906 | 53470.00 | 6.4383 | 100.00 | 31.761 | 37.814 | 0.00027 |
| 1000 | vector | 3 | 200000 | 1374428895.67 | 1253911595.33 | 0.9123 | 29686.67 | 7.6188 | 100.00 | 6.872 | 6.270 | 0.00015 |
| 100000 | scalar | 3 | 2000 | 5488055382.00 | 7403599122.67 | 1.3490 | 2891685.00 | 1.9681 | 100.00 | 27.440 | 37.018 | 0.01446 |
| 100000 | vector | 3 | 2000 | 559468876.00 | 1078758870.67 | 1.9282 | 73001.33 | 0.0554 | 100.00 | 2.797 | 5.394 | 0.00037 |
| 1000000 | scalar | 3 | 200 | 5781514785.00 | 7417438783.00 | 1.2830 | 57307024.00 | 34.3571 | 100.00 | 28.908 | 37.087 | 0.28654 |
| 1000000 | vector | 3 | 200 | 805191048.67 | 1092453995.67 | 1.3568 | 21749726.00 | 14.5483 | 100.00 | 4.026 | 5.462 | 0.10875 |
| 50000000 | scalar | 3 | 30 | 45110886421.33 | 56350414209.00 | 1.2492 | 894634517.00 | 70.8213 | 100.00 | 30.074 | 37.567 | 0.59642 |
| 50000000 | vector | 3 | 30 | 8872663351.00 | 8912907697.33 | 1.0045 | 653876147.00 | 61.0431 | 100.00 | 5.915 | 5.942 | 0.43592 |

Un porcentaje activo menor que 100 indica multiplexacion: perf escala los conteos.
Un denominador de referencias cero produce N/D, no una tasa de cero.
El significado de cache-references/cache-misses depende de la CPU y su PMU;
no equivale necesariamente a fallos L1 ni permite medir ancho de banda por si solo.
Compare IPC, instrucciones y fallos junto con los tiempos del kernel y el tamano N.
Un IPC mayor por si solo no garantiza menor tiempo; no confunda ciclos con milisegundos.
