/* Fase 3, persona 2: llama exclusivamente a sum_array con la ABI de stats.h. */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "stats.h"

int main(int argc, char **argv) {
#ifdef TEST_VECTOR
    /* GCC comprueba tambien que el SO habilite el estado AVX. */
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "SKIP: CPU/SO sin soporte AVX2\n");
        return 77;
    }
#endif
    if (argc != 2) {
        fprintf(stderr, "Uso: %s input.dat\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 2; }
    int32_t n;
    /* Este ejecutable de pruebas admite hasta un millon de elementos. */
    if (fread(&n, sizeof n, 1, f) != 1 || n < 0 || n > 1000000) {
        fprintf(stderr, "Error: N invalido\n");
        fclose(f);
        return 2;
    }
    size_t count = ((size_t)n + 7) / 8 * 8 + 8;
    size_t bytes = count * sizeof(float);
    float *arr = aligned_alloc(32, bytes);
    float *before = malloc(bytes);
    if (!arr || !before) {
        fprintf(stderr, "Error: reserva de memoria\n");
        free(arr); free(before); fclose(f); return 2;
    }
    /* NaN en el relleno revela sumas que incorporan elementos fuera de N. */
    for (size_t i = 0; i < count; ++i) arr[i] = NAN;
    if (fread(arr, sizeof(float), (size_t)n, f) != (size_t)n ||
        fgetc(f) != EOF || ferror(f)) {
        fprintf(stderr, "Error: longitud de archivo incorrecta\n");
        free(arr); free(before); fclose(f); return 2;
    }
    fclose(f);
    memcpy(before, arr, bytes);
    float sum = sum_array(arr, n);
    if (memcmp(arr, before, bytes) != 0) {
        fprintf(stderr, "FAIL: sum_array modifico la entrada\n");
        free(arr); free(before); return 1;
    }
    printf("%.9g\n", sum);
    free(arr);
    free(before);
    return 0;
}
