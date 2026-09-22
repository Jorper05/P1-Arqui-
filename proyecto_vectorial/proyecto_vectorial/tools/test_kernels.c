/* Ejecuta un kernel aislado con entrada y salida alineadas y guardas. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "stats.h"

#define GUARD 8

static int fail(const char *message)
{
    fprintf(stderr, "Error: %s\n", message);
    return 1;
}

int main(int argc, char **argv)
{
    int stats = argc >= 2 && strcmp(argv[1], "stats") == 0;
    int norm = argc >= 2 && strcmp(argv[1], "normalize") == 0;
    if ((!stats && !norm) || (stats && argc != 3) || (norm && argc != 5))
        return fail("uso: test_kernels stats entrada | normalize entrada media sigma");
#ifdef TEST_VECTOR
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "AVX2 no disponible\n");
        return 77;
    }
#endif
    float mean = NAN, sigma = NAN;
    if (norm) {
        char *end;
        mean = strtof(argv[3], &end);
        if (*end || end == argv[3] || !isfinite(mean)) return fail("media invalida");
        sigma = strtof(argv[4], &end);
        if (*end || end == argv[4] || !isfinite(sigma) || sigma < 0)
            return fail("sigma invalida");
    }
    FILE *f = fopen(argv[2], "rb");
    if (!f) return fail("no se pudo abrir la entrada");
    int32_t n;
    if (fread(&n, sizeof(n), 1, f) != 1 || n < 0) {
        fclose(f);
        return fail("cabecera invalida");
    }
    /* El ejecutor se limita a casos pequenos de integracion. */
    if (n > 1000000) {
        fclose(f);
        return fail("N excede el limite de prueba");
    }
    size_t count = ((size_t)n + 7) / 8 * 8 + 2 * GUARD;
    size_t bytes = count * sizeof(float);
    float *input = aligned_alloc(32, bytes);
    float *output = aligned_alloc(32, bytes);
    float *backup = malloc(bytes);
    if (!input || !output || !backup) {
        fclose(f);
        free(input); free(output); free(backup);
        return fail("sin memoria");
    }
    for (size_t i = 0; i < count; ++i) input[i] = output[i] = NAN;
    float *in = input + GUARD, *out = output + GUARD;
    int ok = fread(in, sizeof(float), (size_t)n, f) == (size_t)n;
    ok = ok && fgetc(f) == EOF && !ferror(f);
    fclose(f);
    for (int i = 0; i < n; ++i) ok = ok && isfinite(in[i]);
    if (!ok) {
        free(input); free(output); free(backup);
        return fail("longitud o valores invalidos");
    }
    memcpy(backup, input, bytes);
    /* Cada resultado se rodea de guardas para detectar escrituras de mas. */
    float m[3] = {12345, NAN, -12345}, v[3] = {12345, NAN, -12345};
    float lo[3] = {12345, NAN, -12345}, hi[3] = {12345, NAN, -12345};
    if (stats) compute_stats(in, n, m + 1, v + 1, lo + 1, hi + 1);
    else normalize_array(in, out, n, mean, sigma);
    ok = memcmp(input, backup, bytes) == 0;
    for (size_t i = 0; i < count; ++i)
        if (i < GUARD || i >= GUARD + (size_t)n)
            ok = ok && isnan(output[i]);
    if (stats) {
        float *fields[] = {m, v, lo, hi};
        for (size_t i = 0; i < 4; ++i)
            ok = ok && fields[i][0] == 12345 && fields[i][2] == -12345
                    && isfinite(fields[i][1]);
    } else {
        for (int i = 0; i < n; ++i) ok = ok && isfinite(out[i]);
    }
    if (ok) {
        if (stats) printf("%.9g %.9g %.9g %.9g\n", m[1], v[1], lo[1], hi[1]);
        else {
            for (int i = 0; i < n; ++i) printf("%.9g\n", out[i]);
        }
    }
    free(input); free(output); free(backup);
    return ok ? 0 : fail("entrada modificada, guarda alterada o resultado no finito");
}
