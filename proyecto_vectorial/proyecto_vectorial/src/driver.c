#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <errno.h>
#include <limits.h>
#include <cpuid.h>

#include "stats.h"

#define VEC_ALIGN 32

/* Promedio y desviacion estandar muestral, sin guardar todas las muestras. */
typedef struct {
    double mean;
    double m2;
} timing;

/* Actualiza la media y la dispersion con el algoritmo de Welford.
 * count es el numero de muestras acumuladas, incluida la actual. */
static void record_time(timing *t, double ms, int count) {
    double delta = ms - t->mean;
    t->mean += delta / count;
    t->m2 += delta * (ms - t->mean);
}

static double time_stddev(const timing *t, int count) {
    return count > 1 ? sqrt(fmax(0.0, t->m2 / (count - 1))) : 0.0;
}

static double elapsed_ms(struct timespec start, struct timespec end) {
    return (end.tv_sec - start.tv_sec) * 1000.0 +
           (end.tv_nsec - start.tv_nsec) / 1e6;
}

/* Reloj monotono para medir intervalos sin cambios del reloj civil. */
static int timestamp(struct timespec *t) {
    if (clock_gettime(CLOCK_MONOTONIC, t) == 0) return 1;
    perror("Error: clock_gettime");
    return 0;
}

/* Lectura serializada del TSC. Incluye el costo de las barreras de medicion.
 * Los ticks TSC no equivalen a los ciclos de nucleo contados por perf. */
static uint64_t read_tsc(void) {
    unsigned int a, b, c, d, lo, hi;
    __cpuid(0, a, b, c, d);
    __asm__ volatile ("rdtsc" : "=a" (lo), "=d" (hi) : : "memory");
    __cpuid(0, a, b, c, d);
    __asm__ volatile ("" : : : "memory");
    return ((uint64_t)hi << 32) | lo;
}

/* Reserva memoria con direccion alineada a 32 bytes para los datos AVX2.
 * Comprueba el desbordamiento antes de calcular el tamano y lo redondea
 * a un multiplo de 32, como exige aligned_alloc. Incluso para count=0
 * reserva un bloque minimo; inicializa todo el bloque, incluido el relleno. */
static float *alloc_aligned_floats(size_t count) {
    if (count > (SIZE_MAX - (VEC_ALIGN - 1)) / sizeof(float)) {
        fprintf(stderr, "Error: tamano de arreglo fuera de rango.\n");
        return NULL;
    }
    size_t bytes = count * sizeof(float);
    size_t padded = ((bytes + VEC_ALIGN - 1) / VEC_ALIGN) * VEC_ALIGN;
    if (padded == 0) padded = VEC_ALIGN;
    float *p = aligned_alloc(VEC_ALIGN, padded);
    if (!p) fprintf(stderr, "Error: no se pudo reservar memoria alineada.\n");
    else memset(p, 0, padded);
    return p;
}

/* Linux x86-64: int32 y float32 little endian. No se aceptan bytes extra. */
static float *read_input(const char *path, int *out_n) {
    FILE *f = fopen(path, "rb");
    float *arr = NULL;
    int valid = 0;
    int32_t n = 0;
    if (!f) {
        fprintf(stderr, "Error: no se pudo abrir '%s': %s\n", path, strerror(errno));
        return NULL;
    }
    /* Lee la cabecera int32 y exige un numero positivo de elementos. */
    if (fread(&n, sizeof(n), 1, f) != 1) {
        fprintf(stderr, "Error: archivo de entrada invalido (falta N o fallo de lectura).\n");
        goto done;
    }
    if (n <= 0) {
        fprintf(stderr, "Error: N debe ser mayor que cero (N=%d).\n", (int)n);
        goto done;
    }
    /* Reserva el arreglo alineado y exige exactamente N valores float32. */
    arr = alloc_aligned_floats((size_t)n);
    if (!arr) goto done;
    if (fread(arr, sizeof(*arr), (size_t)n, f) != (size_t)n) {
        fprintf(stderr, "Error: archivo de entrada truncado o fallo de lectura.\n");
        goto done;
    }
    /* Rechaza bytes adicionales y distingue EOF de un error de lectura. */
    if (fgetc(f) != EOF) {
        fprintf(stderr, "Error: contenido sobrante al final del archivo de entrada.\n");
        goto done;
    }
    if (ferror(f)) {
        fprintf(stderr, "Error: fallo al leer el archivo de entrada.\n");
        goto done;
    }
    /* NaN e infinito no se admiten como datos de entrada. */
    for (int i = 0; i < n; ++i) {
        if (!isfinite(arr[i])) {
            fprintf(stderr, "Error: dato no finito en el indice %d.\n", i);
            goto done;
        }
    }
    /* Solo una lectura completa y valida permite devolver el arreglo. */
    valid = 1;
done:
    if (fclose(f) != 0) {
        fprintf(stderr, "Error: fallo al cerrar el archivo de entrada.\n");
        valid = 0;
    }
    if (!valid) {
        free(arr);
        return NULL;
    }
    *out_n = (int)n;
    return arr;
}

/* Guarda el arreglo normalizado en formato binario: int32 N y N float32.
 * Verifica tanto las escrituras como el cierre del archivo. */
static int write_output(const char *path, const float *arr, int n) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "Error: no se pudo crear '%s': %s\n", path, strerror(errno));
        return 0;
    }
    int32_t count = (int32_t)n;
    int ok = fwrite(&count, sizeof(count), 1, f) == 1;
    if (ok) ok = fwrite(arr, sizeof(*arr), (size_t)n, f) == (size_t)n;
    /* fclose tambien comprueba errores al vaciar el buffer. */
    if (fclose(f) != 0) ok = 0;
    if (!ok) fprintf(stderr, "Error: escritura o cierre incompleto de '%s'.\n", path);
    return ok;
}

/* Escribe el resumen de estadisticos y las medias y desviaciones muestrales
 * de las mediciones. Los campos cycles contienen ticks TSC. */
static int write_stats_summary(const char *path, int n, float sum,
                               float mean, float var, float stddev,
                               float min, float max, const timing times[4],
                               const timing cycles[4], int reps) {
    FILE *f = fopen(path, "w");
    if (!f) {
        fprintf(stderr, "Error: no se pudo crear el resumen '%s': %s\n", path, strerror(errno));
        return 0;
    }
    int ok = fprintf(f,
        "n=%d\nsum=%.9g\nmean=%.9g\nvar=%.9g\nstddev=%.9g\nmin=%.9g\nmax=%.9g\n"
        "kernel_ms=%.9f\nrepetitions=%d\n",
        n, sum, mean, var, stddev, min, max, times[3].mean, reps) >= 0;
    const char *names[] = {"sum_array", "compute_stats", "normalize_array", "kernel"};
    for (int i = 0; i < 4 && ok; ++i) {
        if (i < 3) ok = fprintf(f, "%s_ms=%.9f\n", names[i], times[i].mean) >= 0;
        if (ok) ok = fprintf(f, "%s_stddev_ms=%.9f\n", names[i],
                             time_stddev(&times[i], reps)) >= 0;
        if (ok) ok = fprintf(f, "%s_cycles=%.9f\n%s_stddev_cycles=%.9f\n",
                             names[i], cycles[i].mean, names[i],
                             time_stddev(&cycles[i], reps)) >= 0;
    }
    if (fclose(f) != 0) ok = 0;
    if (!ok) fprintf(stderr, "Error: escritura o cierre incompleto del resumen '%s'.\n", path);
    return ok;
}

static int parse_repetitions(const char *text, int *reps) {
    if (!*text) return 0;
    for (const char *p = text; *p; ++p)
        if (*p < '0' || *p > '9') return 0;
    errno = 0;
    char *end;
    long value = strtol(text, &end, 10);
    if (errno == ERANGE || *end || value < 1 || value > INT_MAX) return 0;
    *reps = (int)value;
    return 1;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Uso: %s <input.dat> <output.dat> [repeticiones]\n"
        "  Entrada y salida: int32 N seguido de N floats (little endian).\n"
        "  Repeticiones: entero positivo, por defecto 1; use al menos 30 para medir.\n",
        prog);
}

int main(int argc, char **argv) {
#ifdef REQUIRE_AVX2
    /* GCC comprueba tambien que el SO habilite el estado XMM/YMM. */
    __builtin_cpu_init();
    if (!__builtin_cpu_supports("avx2")) {
        fprintf(stderr, "Error: la version vectorial requiere AVX2 habilitado por la CPU y el sistema operativo. Use bin/norm_scalar.\n");
        return EXIT_FAILURE;
    }
#endif
    if (argc < 3 || argc > 4) {
        usage(argv[0]);
        return EXIT_FAILURE;
    }
    int reps = 1;
    if (argc == 4 && !parse_repetitions(argv[3], &reps)) {
        fprintf(stderr, "Error: repeticiones debe ser un entero entre 1 y %d.\n", INT_MAX);
        return EXIT_FAILURE;
    }

    int result = EXIT_FAILURE;
    int n = 0;
    /* La lectura valida el archivo y devuelve la entrada ya alineada. */
    float *in = read_input(argv[1], &n);
    if (!in) return result;
    /* La salida tambien requiere alineacion de 32 bytes. */
    float *out = alloc_aligned_floats((size_t)n);
    char *summary_path = NULL;
    if (!out) goto done;
    /* Construye la ruta del resumen asociado: <output.dat>.stats.txt.
     * Incluye espacio para el terminador nulo y evita desbordar size_t. */
    const char suffix[] = ".stats.txt";
    size_t path_len = strlen(argv[2]);
    if (path_len > SIZE_MAX - sizeof(suffix)) goto done;
    summary_path = malloc(path_len + sizeof(suffix));
    if (!summary_path) {
        fprintf(stderr, "Error: no se pudo reservar memoria para la ruta del resumen.\n");
        goto done;
    }
    memcpy(summary_path, argv[2], path_len);
    memcpy(summary_path + path_len, suffix, sizeof(suffix));

    float sum = 0.0f, mean = 0.0f, var = 0.0f, min = 0.0f, max = 0.0f;
    float stddev = 0.0f;
    /* Indices 0, 1 y 2: suma, estadisticos y normalizacion; 3: total. */
    timing times[4] = {{0}};
    timing cycles[4] = {{0}};
    /* Repite las llamadas NASM sobre la misma entrada y acumula mediciones.
     * stats.h declara su interfaz; el enlace selecciona la implementacion
     * escalar o vectorial. Las rutinas reciben N elementos utiles, sin relleno. */
    for (int r = 0; r < reps; ++r) {
        struct timespec t0, t1, t2, t3;
        if (!timestamp(&t0)) goto done;
        uint64_t c0 = read_tsc();
        /* NASM: devuelve la suma del arreglo. t0/t1 delimitan el tiempo
         * transcurrido; c0/c1 delimitan los ticks TSC de esta llamada. */
        sum = sum_array(in, n);
        uint64_t c1 = read_tsc();
        if (!timestamp(&t1)) goto done;
        uint64_t c2 = read_tsc();
        /* NASM: escribe media, varianza, minimo y maximo mediante punteros. */
        compute_stats(in, n, &mean, &var, &min, &max);
        uint64_t c3 = read_tsc();
        if (!timestamp(&t2)) goto done;
        double sum_ms = elapsed_ms(t0, t1);
        double stats_ms = elapsed_ms(t1, t2);

        /* Valida los estadisticos antes de calcular la desviacion estandar.
         * Esta validacion y sqrtf quedan fuera de los intervalos medidos. */
        if (!isfinite(sum) || !isfinite(mean) || !isfinite(var) ||
            !isfinite(min) || !isfinite(max) || var < 0.0f) {
            fprintf(stderr, "Error: estadisticos invalidos; revise los kernels o el rango float32.\n");
            goto done;
        }
        stddev = sqrtf(var);
        if (!timestamp(&t2)) goto done;
        uint64_t c4 = read_tsc();
        /* NASM: escribe la normalizacion en out usando media y desviacion.
         * t2 se toma de nuevo para excluir la validacion y sqrtf. */
        normalize_array(in, out, n, mean, stddev);
        uint64_t c5 = read_tsc();
        if (!timestamp(&t3)) goto done;
        double norm_ms = elapsed_ms(t2, t3);
        /* Evita publicar diferencias TSC nulas o no monotonas.
         * Son ticks del contador temporal, no ciclos de nucleo de perf. */
        if (c1 <= c0 || c3 <= c2 || c5 <= c4) {
            fprintf(stderr, "Error: lectura TSC no monotona; no se publican mediciones.\n");
            goto done;
        }
        double sum_cycles = (double)(c1 - c0);
        double stats_cycles = (double)(c3 - c2);
        double norm_cycles = (double)(c5 - c4);
        /* Acumula cada muestra sin guardar un arreglo de mediciones.
         * Los intervalos incluyen el costo de instrumentacion y barreras. */
        record_time(&cycles[0], sum_cycles, r + 1);
        record_time(&cycles[1], stats_cycles, r + 1);
        record_time(&cycles[2], norm_cycles, r + 1);
        record_time(&cycles[3], sum_cycles + stats_cycles + norm_cycles, r + 1);
        record_time(&times[0], sum_ms, r + 1);
        record_time(&times[1], stats_ms, r + 1);
        record_time(&times[2], norm_ms, r + 1);
        /* Total por repeticion: suma de las tres llamadas NASM.
         * Excluye lectura, escritura, sqrtf y validaciones. */
        record_time(&times[3], sum_ms + stats_ms + norm_ms, r + 1);
    }
    /* Comprueba todos los elementos normalizados antes de escribirlos. */
    for (int i = 0; i < n; ++i) {
        if (!isfinite(out[i])) {
            fprintf(stderr, "Error: salida no finita en el indice %d.\n", i);
            goto done;
        }
    }
    /* Guarda el arreglo completo y su resumen solo tras validar la salida.
     * Cualquier error conserva EXIT_FAILURE y conduce a la limpieza. */
    if (!write_output(argv[2], out, n)) goto done;
    if (!write_stats_summary(summary_path, n, sum, mean, var, stddev,
                             min, max, times, cycles, reps)) goto done;

    /* Muestra los estadisticos y el resumen de rendimiento en la consola. */
    printf("N        = %d\nSuma     = %.6f\nMedia    = %.6f\n"
           "Varianza = %.6f\nStdDev   = %.6f\nMinimo   = %.6f\nMaximo   = %.6f\n",
           n, sum, mean, var, stddev, min, max);
    const char *names[] = {"sum_array", "compute_stats", "normalize_array"};
    for (int i = 0; i < 3; ++i)
        printf("%s: %.9f ms (desviacion muestral: %.9f ms)\n", names[i],
               times[i].mean, time_stddev(&times[i], reps));
    printf("Tiempo promedio del kernel (%d rep.): %.6f ms\n", reps, times[3].mean);
    printf("Desviacion muestral del kernel: %.9f ms\n", time_stddev(&times[3], reps));
    printf("Ciclos TSC promedio del kernel: %.3f (desviacion muestral: %.3f)\n",
           cycles[3].mean, time_stddev(&cycles[3], reps));
    result = EXIT_SUCCESS;
done:
    /* Punto comun de liberacion, tanto en exito como en error.
     * free acepta NULL y libera tambien bloques obtenidos con aligned_alloc. */
    free(summary_path);
    free(out);
    free(in);
    return result;
}
