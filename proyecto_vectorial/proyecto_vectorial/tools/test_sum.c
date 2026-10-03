/* Prueba independiente de sum_array.
 * Ejecuta el kernel sobre un archivo y comprueba que no modifique la entrada
 * ni el relleno, y que devuelva una suma finita. Publica el resultado para
 * que tools/test_sum.py compruebe su exactitud contra la referencia.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "stats.h"

/* Alineacion del arreglo para la implementacion vectorial. */
#define VEC_ALIGN 32

static float *alloc_aligned_floats(size_t count, size_t *reserved)
{
    /* Reservar tambien ocho floats de guarda y evitar desbordamientos.
     * El limite contempla los elementos utiles, la guarda y el redondeo. */
    if (count > (SIZE_MAX - (VEC_ALIGN - 1)) / sizeof(float) - 8)
        return NULL;

    /* aligned_alloc exige un tamano multiplo de 32. Incluso para count=0
     * hay memoria reservada gracias a los ocho elementos de guarda. */
    size_t bytes = (count + 8) * sizeof(float);
    size_t padded = ((bytes + VEC_ALIGN - 1) / VEC_ALIGN) * VEC_ALIGN;
    float *ptr = aligned_alloc(VEC_ALIGN, padded);
    if (ptr == NULL)
        return NULL;

    /* Si NASM incorpora el relleno a la suma, el resultado sera NaN.
     * La lectura del archivo sustituye solo los count elementos utiles.
     * Esta guarda ayuda a detectar sumas que exceden N, pero no detecta
     * todas las lecturas fuera de limites ni sustituye proteccion de memoria. */
    for (size_t i = 0; i < padded / sizeof(float); i++)
        ptr[i] = NAN;

    /* Devuelve los bytes de todo el bloque para copiarlo y compararlo. */
    *reserved = padded;
    return ptr;
}

int main(int argc, char **argv)
{
    /* Unico argumento: archivo de entrada del caso seleccionado en Python. */
    if (argc != 2) {
        fprintf(stderr, "Uso: %s <input.dat>\n", argv[0]);
        return EXIT_FAILURE;
    }

#ifdef TEST_VECTOR
    /* Compilar este control sin -mavx2; GCC comprueba CPU y soporte del SO.
     * El codigo 77 informa que no se pudo validar AVX2; no es un PASS. */
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "AVX2 no disponible en esta CPU/sistema operativo\n");
        return 77;
    }
#endif

    FILE *f = fopen(argv[1], "rb");
    if (f == NULL) {
        fprintf(stderr, "Error: no se pudo abrir %s\n", argv[1]);
        return EXIT_FAILURE;
    }

    /* Exige cabecera int32 completa y N no negativo. Admite N=0 para
     * probar sum_array directamente, aunque el driver principal lo rechaza. */
    int32_t n;
    if (fread(&n, sizeof(n), 1, f) != 1 || n < 0) {
        fprintf(stderr, "Error: cabecera o N invalido\n");
        fclose(f);
        return EXIT_FAILURE;
    }

    /* Linux x86-64: int32 y float32 nativos coinciden con little endian.
     * Aprobar el formato exige exactamente N*4 bytes despues de la cabecera:
     * rechaza datos truncados y bytes adicionales antes de llamar a NASM. */
    long start = ftell(f);
    if (start < 0 || fseek(f, 0, SEEK_END) != 0) {
        fprintf(stderr, "Error: no se pudo comprobar el archivo\n");
        fclose(f);
        return EXIT_FAILURE;
    }
    long end = ftell(f);
    if (end < start || (uint64_t)(end - start) != (uint64_t)n * 4 ||
        fseek(f, start, SEEK_SET) != 0) {
        fprintf(stderr, "Error: longitud del archivo no coincide con N\n");
        fclose(f);
        return EXIT_FAILURE;
    }

    /* Prepara memoria alineada y relleno NaN para probar tambien los casos
     * cortos y los remanentes del bucle vectorial que seleccione Python. */
    size_t reserved;
    float *arr = alloc_aligned_floats((size_t)n, &reserved);
    if (arr == NULL) {
        fprintf(stderr, "Error: no se pudo reservar memoria alineada\n");
        fclose(f);
        return EXIT_FAILURE;
    }
    /* La lectura debe obtener todos los elementos sin error de archivo.
     * Este auxiliar no valida individualmente la finitud de los datos. */
    if (fread(arr, sizeof(float), (size_t)n, f) != (size_t)n || ferror(f)) {
        fprintf(stderr, "Error: archivo truncado o error de lectura\n");
        free(arr);
        fclose(f);
        return EXIT_FAILURE;
    }
    fclose(f);

    /* Copia de control de TODO el bloque, incluidas guarda y alineacion.
     * Permite detectar cualquier cambio de bytes en esa region reservada. */
    float *copia = malloc(reserved);
    if (copia == NULL) {
        fprintf(stderr, "Error: no se pudo reservar la copia de control\n");
        free(arr);
        return EXIT_FAILURE;
    }
    memcpy(copia, arr, reserved);

    /* N=0 es valido aqui: la suma vacia debe ser exactamente cero.
     * Este archivo publica el valor; la prueba Python debe verificar ese
     * cero y la exactitud de las sumas para los demas casos. */
    float suma = sum_array(arr, n);
    int modificada = memcmp(arr, copia, reserved) != 0;
    free(copia);
    free(arr);

    /* Criterio local 1: sum_array conserva entrada y relleno byte por byte. */
    if (modificada) {
        fprintf(stderr, "Error: sum_array modifico la entrada o el relleno\n");
        return EXIT_FAILURE;
    }
    /* Criterio local 2: devuelve un valor finito, sin NaN ni infinito.
     * Una suma finita incorrecta requiere la comparacion numerica en Python. */
    if (!isfinite(suma)) {
        fprintf(stderr, "Error: suma no finita (NaN o infinito)\n");
        return EXIT_FAILURE;
    }
    /* Nueve cifras significativas permiten representar el resultado float32
     * para su comparacion externa. Cero indica que los controles locales pasan. */
    printf("%.9g\n", suma);
    return EXIT_SUCCESS;
}
