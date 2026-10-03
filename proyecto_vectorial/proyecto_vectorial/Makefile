# =========================================================
# Makefile - Normalizador estadistico vectorizado
# =========================================================

# Herramientas: ?= permite sobrescribir la opcion desde el entorno o make.
CC        := gcc
NASM      := nasm
PYTHON    ?= python3
PERF      ?= perf

# Benchmark: tamanos N y muestras independientes por version y tamano.
BENCH_SIZES ?= 1000 100000 1000000 50000000
BENCH_REPS  ?= 30
# perf usa los mismos tamanos que el benchmark. PERF_REPS es el minimo de repeticiones
# del kernel por proceso; tools/measure.py lo aumenta para N pequenos.
# El numero efectivo esta sujeto al limite definido en measure.py.
PERF_SIZES  ?= $(BENCH_SIZES)
PERF_REPS   ?= 30
# Argumentos adicionales de tools/measure.py, no opciones directas de perf stat.
PERF_FLAGS  ?=
# Procesos independientes de perf por version y tamano.
PERF_RUNS   ?= 3
SEED        ?= 123
# Cada ejecucion crea un directorio run-* para sus muestras y reportes.
BENCH_RESULTS ?= benchmark/results
PERF_RESULTS  ?= benchmark/results/perf

# GCC: C GNU11, avisos, optimizacion O2 y simbolos para depuracion.
# NASM: objetos ELF64 con informacion de depuracion DWARF.
# -lm enlaza las funciones matematicas utilizadas por el driver y pruebas.
CFLAGS    := -std=gnu11 -Wall -Wextra -O2 -g
NASMFLAGS := -f elf64 -g -F dwarf
LDFLAGS   := -lm

SRC_DIR    := src
INC_DIR    := include
OBJ_DIR    := obj
BIN_DIR    := bin

ASM_SCALAR := asm/scalar/stats_scalar.asm

ASM_VECTOR := asm/vector/stats_vector.asm

# Dos objetos del mismo driver: el vectorial activa la comprobacion AVX2.
DRIVER_OBJ := $(OBJ_DIR)/driver.o
VECTOR_DRIVER_OBJ := $(OBJ_DIR)/driver_vector.o
SCALAR_OBJ := $(OBJ_DIR)/stats_scalar.o
VECTOR_OBJ := $(OBJ_DIR)/stats_vector.o

TEST_SCALAR_OBJ := $(OBJ_DIR)/test_sum_scalar.o
TEST_VECTOR_OBJ := $(OBJ_DIR)/test_sum_vector.o

# Objetivos de accion: se ejecutan aunque exista un archivo con su nombre.
.PHONY: all scalar vector test benchmark perf help clean distclean dirs run-scalar run-vector test-sum
.PHONY: generate-inputs generate-inputs-large test-input test-input-large

# Objetivo predeterminado: construye ambos normalizadores.
all: scalar vector

scalar: $(BIN_DIR)/norm_scalar

vector: $(BIN_DIR)/norm_vector

# Prerrequisito de orden (| dirs): crea carpetas sin forzar recompilaciones
# por cambios en sus fechas. Los comandos de las recetas llevan tabulacion.
dirs:
	@mkdir -p $(OBJ_DIR) $(BIN_DIR) data

# Compilacion del programa principal: -c genera objetos sin enlazar.
# Una modificacion en driver.c o stats.h reconstruye el objeto correspondiente.
# $< es el primer prerrequisito; $@ es el archivo objetivo.
$(DRIVER_OBJ): $(SRC_DIR)/driver.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

$(VECTOR_DRIVER_OBJ): $(SRC_DIR)/driver.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -DREQUIRE_AVX2 -I$(INC_DIR) -c $< -o $@

# Ensamblado de los kernels: cada fuente NASM produce su propio objeto.
$(SCALAR_OBJ): $(ASM_SCALAR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

$(VECTOR_OBJ): $(ASM_VECTOR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

# Enlace de los normalizadores: une el driver con la implementacion elegida.
# $^ contiene los prerrequisitos normales, sin repetirlos y sin incluir dirs.
$(BIN_DIR)/norm_scalar: $(DRIVER_OBJ) $(SCALAR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/norm_vector: $(VECTOR_DRIVER_OBJ) $(VECTOR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Ejecucion del programa principal con 10 repeticiones internas del kernel.
# data/input.dat debe existir; estos objetivos no generan la entrada.
run-scalar: $(BIN_DIR)/norm_scalar
	./$(BIN_DIR)/norm_scalar data/input.dat data/output_scalar.dat 10

run-vector: $(BIN_DIR)/norm_vector
	./$(BIN_DIR)/norm_vector data/input.dat data/output_vector.dat 10

# Compilacion de las pruebas de sum_array; TEST_VECTOR selecciona la variante
# vectorial del programa de prueba. Cada objeto se enlaza con su kernel NASM.
$(TEST_SCALAR_OBJ): tools/test_sum.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

$(TEST_VECTOR_OBJ): tools/test_sum.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -DTEST_VECTOR -I$(INC_DIR) -c $< -o $@

# Enlace de las pruebas con cada kernel
$(BIN_DIR)/test_sum_scalar: $(TEST_SCALAR_OBJ) $(SCALAR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/test_sum_vector: $(TEST_VECTOR_OBJ) $(VECTOR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Comparacion de sum_array contra NumPy
test-sum: $(BIN_DIR)/test_sum_scalar $(BIN_DIR)/test_sum_vector
	$(PYTHON) tools/test_sum.py

# Generacion y validacion de entradas independiente de NASM.
# small incluye casos borde; large incluye archivos de hasta 50 millones.
# Estos comandos usan la semilla literal 123, no la variable SEED.
generate-inputs:
	$(PYTHON) tools/gen_input.py --suite small --out-dir data/inputs --seed 123

generate-inputs-large:
	$(PYTHON) tools/gen_input.py --suite large --out-dir data/inputs --seed 123

test-input:
	$(PYTHON) tools/test_input.py

test-input-large:
	$(PYTHON) tools/test_input.py --large

# Limpieza de objetos y ejecutables: conserva entradas y resultados medidos,
# incluidos data/, output/ y benchmark/results/.
clean:
	rm -rf $(OBJ_DIR) $(BIN_DIR)

# Ademas elimina output/. No elimina BENCH_RESULTS ni PERF_RESULTS por
# variable: sus rutas predeterminadas benchmark/results/ se conservan.
distclean: clean
	rm -rf output

# Verificacion completa contra NumPy y entre implementaciones.
# Comprueba estadisticos, salida normalizada completa y casos especiales.
.PHONY: test-reference
test-reference: all
	$(PYTHON) tools/verify_reference.py --suite

# Pruebas aisladas de estadisticos y normalizacion
$(OBJ_DIR)/test_kernels_scalar.o: tools/test_kernels.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

$(OBJ_DIR)/test_kernels_vector.o: tools/test_kernels.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -DTEST_VECTOR -I$(INC_DIR) -c $< -o $@

$(BIN_DIR)/test_kernels_scalar: $(OBJ_DIR)/test_kernels_scalar.o $(SCALAR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/test_kernels_vector: $(OBJ_DIR)/test_kernels_vector.o $(VECTOR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Integra el driver y los kernels; construye los ejecutables que requiere.
.PHONY: test-integration
test-integration: all $(BIN_DIR)/test_kernels_scalar $(BIN_DIR)/test_kernels_vector
	$(PYTHON) tools/test_integration.py

# Comprueba el propio verificador para detectar errores en sus criterios.
.PHONY: test-verifier
test-verifier:
	$(PYTHON) tools/test_verify_reference.py

# Agrupa las verificaciones habituales; no incluye test-input-large ni test-perf.
# Un fallo devuelve error a make. Con -j, objetivos independientes pueden
# ejecutarse en paralelo y alguno puede estar ya en marcha cuando ocurre un fallo.
test: test-input test-verifier test-sum test-reference test-integration

# Las mediciones usan tiempos y ticks TSC publicados por el driver.
# measure.py verifica la correccion antes de medir y guarda muestras,
# metadatos, resumenes y grafico; el tiempo medido corresponde al kernel.
benchmark: all
	$(PYTHON) tools/measure.py benchmark --sizes $(BENCH_SIZES) --reps $(BENCH_REPS) --seed $(SEED) --results-dir "$(BENCH_RESULTS)"

# perf stat cuenta el proceso completo, incluida E/S. measure.py ajusta las
# repeticiones internas para amortizar esos costes, comprueba acceso a eventos
# y conserva contadores, comandos, logs y tablas. No cambia permisos del sistema.
perf: all
	$(PYTHON) tools/measure.py perf --sizes $(PERF_SIZES) --reps $(PERF_REPS) --seed $(SEED) --perf "$(PERF)" --perf-runs $(PERF_RUNS) --results-dir "$(PERF_RESULTS)" $(PERF_FLAGS)

# Lista comandos y variables disponibles; @ oculta el comando echo en la salida.
help:
	@echo "make / make scalar / make vector: compilar"
	@echo "make test: ejecutar todas las pruebas"
	@echo "make benchmark: guardar tiempos (ms y ciclos TSC), speedup y grafico en $(BENCH_RESULTS)/run-*/"
	@echo "make perf: guardar contadores y tabla (todos los tamanos) en $(PERF_RESULTS)/run-*/"
	@echo "make test-perf: probar el analisis de benchmark y perf sin PMU ni ejecutables"
	@echo "make clean: eliminar obj/ y bin/; conservar data/ y output/"
	@echo "make distclean: clean y ademas eliminar output/"
	@echo "Variables: BENCH_SIZES, BENCH_REPS, BENCH_RESULTS, PERF_SIZES, PERF_REPS, PERF_RUNS, PERF_RESULTS, PERF_FLAGS, SEED, PYTHON, PERF"

# Validacion del analisis sin requerir acceso a la PMU ni compilar ejecutables.
# Descubre y ejecuta los archivos test_*.py de la carpeta benchmark.
.PHONY: test-perf
test-perf:
	$(PYTHON) -m unittest discover -s benchmark -p 'test_*.py' -v
