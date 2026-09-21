#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "stats.h"

#define VEC_ALIGN 32

static float *alloc_aligned_floats(size_t count, size_t *reserved)
{
    /* Reservar tambien ocho floats de guarda y evitar desbordamientos. */
    if (count > (SIZE_MAX - (VEC_ALIGN - 1)) / sizeof(float) - 8)
        return NULL;

    size_t bytes = (count + 8) * sizeof(float);
    size_t padded = ((bytes + VEC_ALIGN - 1) / VEC_ALIGN) * VEC_ALIGN;
    float *ptr = aligned_alloc(VEC_ALIGN, padded);
    if (ptr == NULL)
        return NULL;

    /* Si NASM incorpora el relleno a la suma, el resultado sera NaN. */
    for (size_t i = 0; i < padded / sizeof(float); i++)
        ptr[i] = NAN;

    *reserved = padded;
    return ptr;
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "Uso: %s <input.dat>\n", argv[0]);
        return EXIT_FAILURE;
    }

#ifdef TEST_VECTOR
    /* Compilar este control sin -mavx2; GCC comprueba CPU y soporte del SO. */
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

    int32_t n;
    if (fread(&n, sizeof(n), 1, f) != 1 || n < 0) {
        fprintf(stderr, "Error: cabecera o N invalido\n");
        fclose(f);
        return EXIT_FAILURE;
    }

    /* Linux x86-64: int32 y float32 nativos coinciden con little endian. */
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

    size_t reserved;
    float *arr = alloc_aligned_floats((size_t)n, &reserved);
    if (arr == NULL) {
        fprintf(stderr, "Error: no se pudo reservar memoria alineada\n");
        fclose(f);
        return EXIT_FAILURE;
    }
    if (fread(arr, sizeof(float), (size_t)n, f) != (size_t)n || ferror(f)) {
        fprintf(stderr, "Error: archivo truncado o error de lectura\n");
        free(arr);
        fclose(f);
        return EXIT_FAILURE;
    }
    fclose(f);

    float *copia = malloc(reserved);
    if (copia == NULL) {
        fprintf(stderr, "Error: no se pudo reservar la copia de control\n");
        free(arr);
        return EXIT_FAILURE;
    }
    memcpy(copia, arr, reserved);

    /* N=0 es valido aqui: la suma vacia debe ser exactamente cero. */
    float suma = sum_array(arr, n);
    int modificada = memcmp(arr, copia, reserved) != 0;
    free(copia);
    free(arr);

    if (modificada) {
        fprintf(stderr, "Error: sum_array modifico la entrada o el relleno\n");
        return EXIT_FAILURE;
    }
    if (!isfinite(suma)) {
        fprintf(stderr, "Error: suma no finita (NaN o infinito)\n");
        return EXIT_FAILURE;
    }
    printf("%.9g\n", suma);
    return EXIT_SUCCESS;
}
