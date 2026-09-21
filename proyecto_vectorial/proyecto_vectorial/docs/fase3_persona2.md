# Fase 3 de la persona 2

Se verifica la funcion existente `sum_array` de las versiones escalar y AVX2
contra NumPy en float32. El alcance corresponde a las imagenes de Fase 3 del
documento Fases de trabajo personal 1-5 y a distribucion.jpeg.

## Ubicacion y responsabilidades

El Makefile funcional del repositorio esta en
`proyecto_vectorial/proyecto_vectorial/`. Todos los comandos siguientes, salvo
el primer `cd`, se ejecutan desde ese directorio. Las copias `src/libstats_*.asm`
en la raiz del repositorio no son las que utiliza este Makefile.

La persona 2 prepara entradas, integra C con NASM y valida resultados. La
persona 1 mantiene los algoritmos NASM. No se cambia el algoritmo de suma.

## Archivos

- `tests/sum_probe.c`: reserva memoria alineada a 32 bytes y llama solamente a
  `sum_array`, con la firma de `include/stats.h`. No calcula estadisticos ni
  normaliza. Comprueba que la entrada no sea modificada y rellena con NaN el
  espacio posterior a N para detectar su incorporacion accidental a la suma.
  Esto no sustituye una prueba completa de seguridad de memoria.
- `tools/test_sum_phase3.py`: genera entradas binarias little endian, ejecuta
  ambas versiones, calcula la referencia NumPy y escribe la tabla CSV.
- `Makefile`: agrega `bin/sum_scalar`, `bin/sum_vector` y `test-phase3`.
- `src/driver.c`: rechaza N <= 0 antes de llamar a cualquier kernel.
- `asm/vector/stats_vector.asm`: corrige seis copias entre registros escritas
  como `vmovss xmmA, xmmB`, que no tienen esa forma valida en NASM. Se usa
  `vmovaps xmmA, xmmB`: copia los 128 bits, conservando el float inferior que
  utiliza el algoritmo. Entre registros no requiere alineacion de memoria.

## Ejecutar en Linux

Requisitos: x86-64 Linux, GCC, make, NASM >= 2.15 y Python 3 con NumPy.
Para completar la comparacion vectorial, la CPU y el sistema operativo deben
permitir AVX2.

Desde la raiz del repositorio:

```bash
cd proyecto_vectorial/proyecto_vectorial
make test-phase3
```

El resultado esperado es `32 casos de suma; 0 fallos; 0 omisiones AVX2`, mas
los dos PASS de rechazo controlado de N=0. La tabla generada esta en
`data/fase3/resultados.csv`. Las entradas tambien quedan en `data/fase3/`.
Para ejecutar un caso individual despues de compilar:

```bash
./bin/sum_scalar data/fase3/secuencia_15.dat
./bin/sum_vector data/fase3/secuencia_15.dat
```

Ambos deben imprimir 120. El programa de prueba acepta N=0; el normalizador
completo debe rechazarlo. No son comportamientos contradictorios: la suma
vacia vale cero, mientras que media y varianza requieren N positivo.

## Comparaciones y cobertura

Se prueban N=0, 1, 7, 8, 15 y 16 con secuencias, negativos, constantes, signos
mixtos y datos pseudoaleatorios con semilla 2026. Se agregan cancelacion exacta
y magnitudes grandes finitas para sumar 32 filas. Las cinco filas con N=0
representan el mismo arreglo vacio, no cinco entradas distintas.

Cada resultado se compara contra NumPy y las versiones se comparan entre si:
`abs(obtenido - referencia) <= 1e-4 * abs(referencia)`. Si la referencia es cero,
se exige cero exacto. NaN e infinito no pasan. Las pequenas diferencias de
redondeo por orden de suma se permiten dentro de esa tolerancia.

N=7 prueba solo el remanente; N=8 un bloque; N=15 un bloque mas siete elementos;
N=16 dos bloques. Una CPU sin AVX2 se informa como SKIP_AVX2 y el script termina
con codigo 77; make informa un resultado no exitoso, nunca un PASS completo.

## Evidencia de ejecucion

Ejecucion realizada el 21 de septiembre de 2026 sobre la base Git `c5455eb`,
con los cambios de esta rama. Entorno: Linux x86-64, Intel Xeon E5-2673 v4,
GCC 13.3.0, NASM 2.16.01 y NumPy 2.3.5. Se obtuvieron 32 PASS de suma,
cero omisiones y dos PASS del rechazo de N=0 por los normalizadores.
El CSV adjunto `fase3_resultados.csv` conserva los valores obtenidos.

Resumen de la familia secuencia, con entrada 1, 2, ..., N:

| N | Escalar | AVX2 | NumPy | Correcto |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | PASS |
| 1 | 1 | 1 | 1 | PASS |
| 7 | 28 | 28 | 28 | PASS |
| 8 | 36 | 36 | 36 | PASS |
| 15 | 120 | 120 | 120 | PASS |
| 16 | 136 | 136 | 136 | PASS |

Este resultado valida la fase 3 para estas entradas. No certifica
`compute_stats`, `normalize_array`, todos los valores extremos de float32,
el rendimiento ni la evidencia GDB de las fases posteriores.
