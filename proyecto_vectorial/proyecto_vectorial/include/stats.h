#ifndef STATS_H
#define STATS_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Interfaz comun de asm/scalar/stats_scalar.asm y
 * asm/vector/stats_vector.asm. Ambas versiones conservan estas firmas.
 *
 * Convencion System V AMD64 ABI:
 *   Enteros/punteros: rdi, rsi, rdx, rcx, r8, r9.
 *   Flotantes: xmm0, xmm1, xmm2, ... (asignacion independiente).
 *   Retorno float: xmm0.
 *
 * Requisitos comunes del llamador:
 *   - n >= 0; los tamanos negativos quedan fuera del contrato.
 *   - Para n > 0, los arreglos contienen al menos n floats accesibles.
 *   - El proyecto entrega los arreglos alineados a 32 bytes mediante
 *     aligned_alloc. Se mantiene este requisito comun para permitir
 *     cargas/almacenamientos AVX alineados (vmovaps). Las instrucciones
 *     vmovups admiten direcciones sin esa alineacion, pero su uso depende
 *     de la implementacion NASM seleccionada.
 *   - n no necesita ser multiplo de 8: el kernel vectorial procesa
 *     tambien el remanente. El relleno de memoria no cuenta como datos.
 *   - Los datos deben ser finitos y su rango debe permitir calculos float32.
 *     Estos kernels no devuelven codigos de error ni validan el archivo.
 *   - La version vectorial requiere soporte AVX2 de CPU y sistema operativo.
 *   - El orden de acumulacion puede producir diferencias de redondeo
 *     entre las versiones escalar y vectorial.
 */

/*
 * sum_array: calcula la suma de los n elementos sin modificar arr.
 *
 * Parametros:
 *   arr: arreglo de entrada de solo lectura, alineado a 32 bytes.
 *   n: numero de elementos utiles.
 * Retorno:
 *   Suma en float; para n == 0 devuelve 0.0f sin leer arr.
 * ABI:
 *   rdi = arr, esi = n; retorno en xmm0.
 */
float sum_array(const float *arr, int n);

/*
 * compute_stats: calcula estadisticos sin modificar arr.
 *
 * Parametros:
 *   arr: arreglo de entrada de solo lectura, alineado a 32 bytes.
 *   n: numero de elementos utiles.
 *   mean, var, min, max: punteros de salida validos, escribibles y
 *     distintos entre si; no deben solaparse con arr. Cada uno apunta
 *     a un float con alineacion natural; no requiere alineacion de 32 bytes.
 * Retorno:
 *   Ninguno (void); escribe los cuatro resultados mediante los punteros.
 *   mean = sum(arr[i]) / n.
 *   var = sum((arr[i] - mean)^2) / n (varianza poblacional).
 *   min y max son los extremos del arreglo.
 * Casos especiales:
 *   n == 0: escribe 0.0f en las cuatro salidas sin leer arr; los
 *     punteros de salida siguen siendo obligatorios.
 *   n == 1 o datos constantes: la varianza matematica es cero;
 *     los resultados calculados estan sujetos al redondeo float32.
 * ABI:
 *   rdi = arr, esi = n, rdx = mean, rcx = var, r8 = min, r9 = max.
 */
void compute_stats(const float *arr, int n,
                    float *mean, float *var, float *min, float *max);

/*
 * normalize_array: escribe la normalizacion de los n elementos en out.
 *
 * Parametros:
 *   in: arreglo de entrada de solo lectura, alineado a 32 bytes.
 *   out: arreglo escribible de al menos n floats, alineado a 32 bytes.
 *     Utilizar arreglos separados sin solapamiento, como hace driver.c.
 *   n: numero de elementos utiles.
 *   mean: media finita utilizada para centrar los datos.
 *   stddev: desviacion estandar finita y no negativa, normalmente sqrt(var).
 * Retorno:
 *   Ninguno (void); para stddev > 0 escribe
 *     out[i] = (in[i] - mean) / stddev.
 * Casos especiales:
 *   n == 0: no lee ni escribe elementos.
 *   stddev == 0.0f: copia in[i] a out[i], sin dividir por cero.
 *     Por contrato, los datos constantes se copian; no se fuerzan a cero.
 * ABI:
 *   rdi = in, rsi = out, edx = n, xmm0 = mean, xmm1 = stddev.
 */
void normalize_array(const float *in, float *out, int n,
                      float mean, float stddev);

#ifdef __cplusplus
}
#endif

#endif /* STATS_H */
