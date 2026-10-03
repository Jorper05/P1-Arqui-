/* Ejecuta un kernel aislado con entrada y salida alineadas y guardas.
 * Este auxiliar valida integridad de memoria y resultados finitos.
 * test_integration.py compara los valores publicados contra la referencia
 * y aplica las tolerancias; este archivo no verifica por si solo la formula.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "stats.h"

/* Ocho floats ocupan 32 bytes: las guardas previas mantienen la alineacion
 * de los punteros in/out que se entregan al kernel. */
#define GUARD 8

static int fail(const char *message)
{
    fprintf(stderr, "Error: %s\n", message);
    return 1;
}

int main(int argc, char **argv)
{
    /* Selecciona compute_stats o normalize_array, sin encadenarlos.
     * Exige el numero de argumentos propio de cada prueba. */
    int stats = argc >= 2 && strcmp(argv[1], "stats") == 0;
    int norm = argc >= 2 && strcmp(argv[1], "normalize") == 0;
    if ((!stats && !norm) || (stats && argc != 3) || (norm && argc != 5))
        return fail("uso: test_kernels stats entrada | normalize entrada media sigma");
#ifdef TEST_VECTOR
    /* Evita ejecutar la variante AVX2 si no esta disponible. El codigo 77
     * indica validacion incompleta; no representa una prueba aprobada. */
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "AVX2 no disponible\n");
        return 77;
    }
#endif
    float mean = NAN, sigma = NAN;
    if (norm) {
        /* La prueba de normalizacion recibe media y sigma externos:
         * permite aislarla de posibles errores en compute_stats.
         * Exige numeros completos, finitos y sigma no negativa; admite cero
         * para probar el contrato de copia sin division. */
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
    /* Admite N=0 para probar los kernels directamente. El driver principal
     * lo rechaza, pero aqui stats debe escribir ceros y normalize no acceder
     * a elementos. La referencia Python comprueba esos resultados concretos. */
    if (fread(&n, sizeof(n), 1, f) != 1 || n < 0) {
        fclose(f);
        return fail("cabecera invalida");
    }
    /* El ejecutor se limita a casos pequenos de integracion. */
    if (n > 1000000) {
        fclose(f);
        return fail("N excede el limite de prueba");
    }
    /* Redondea N a ocho floats y agrega guardas anteriores y posteriores.
     * bytes es multiplo de 32, como exige aligned_alloc. N permanece intacto:
     * el relleno no forma parte de los elementos utiles que procesa NASM. */
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
    /* NaN marca guardas y relleno; tambien permite detectar salidas utiles
     * que el kernel deje sin escribir. No es una pagina de proteccion:
     * las guardas no detectan todas las lecturas/escrituras fuera de limites. */
    for (size_t i = 0; i < count; ++i) input[i] = output[i] = NAN;
    float *in = input + GUARD, *out = output + GUARD;
    /* Aprobar la lectura exige N floats finitos, EOF inmediato y sin error.
     * El formato se interpreta de forma nativa en Linux x86-64 little endian. */
    int ok = fread(in, sizeof(float), (size_t)n, f) == (size_t)n;
    ok = ok && fgetc(f) == EOF && !ferror(f);
    fclose(f);
    for (int i = 0; i < n; ++i) ok = ok && isfinite(in[i]);
    if (!ok) {
        free(input); free(output); free(backup);
        return fail("longitud o valores invalidos");
    }
    /* Copia todo el bloque de entrada, incluidas guardas y relleno, para
     * exigir que el kernel lo conserve byte por byte. */
    memcpy(backup, input, bytes);
    /* Cada resultado se rodea de guardas para detectar escrituras de mas.
     * El float central inicia en NaN: debe quedar escrito con un valor finito.
     * Estos punteros escalares no necesitan alineacion de 32 bytes. */
    float m[3] = {12345, NAN, -12345}, v[3] = {12345, NAN, -12345};
    float lo[3] = {12345, NAN, -12345}, hi[3] = {12345, NAN, -12345};
    if (stats) compute_stats(in, n, m + 1, v + 1, lo + 1, hi + 1);
    else normalize_array(in, out, n, mean, sigma);
    /* Criterio comun: ninguna modificacion en la entrada. */
    ok = memcmp(input, backup, bytes) == 0;
    /* Fuera de los N elementos de salida, guardas y relleno deben seguir
     * siendo NaN. Detecta escrituras que los cambien a valores no NaN. */
    for (size_t i = 0; i < count; ++i)
        if (i < GUARD || i >= GUARD + (size_t)n)
            ok = ok && isnan(output[i]);
    if (stats) {
        /* Aprobar stats exige cuatro resultados finitos y ambos centinelas
         * intactos en cada resultado. La exactitud se evalua luego en Python. */
        float *fields[] = {m, v, lo, hi};
        for (size_t i = 0; i < 4; ++i)
            ok = ok && fields[i][0] == 12345 && fields[i][2] == -12345
                    && isfinite(fields[i][1]);
    } else {
        /* Aprobar normalize exige que TODOS los N elementos sean finitos.
         * La formula y el caso sigma=0 se contrastan luego con la referencia. */
        for (int i = 0; i < n; ++i) ok = ok && isfinite(out[i]);
    }
    if (ok) {
        /* Publica nueve cifras significativas para transportar float32.
         * stats: media, varianza, minimo y maximo. normalize: arreglo completo. */
        if (stats) printf("%.9g %.9g %.9g %.9g\n", m[1], v[1], lo[1], hi[1]);
        else {
            for (int i = 0; i < n; ++i) printf("%.9g\n", out[i]);
        }
    }
    /* Libera todos los bloques. Cero indica que los controles locales pasan;
     * cualquier alteracion detectada o resultado no finito devuelve uno. */
    free(input); free(output); free(backup);
    return ok ? 0 : fail("entrada modificada, guarda alterada o resultado no finito");
}
