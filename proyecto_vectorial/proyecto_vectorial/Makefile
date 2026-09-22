# =========================================================
# Makefile - Normalizador estadistico vectorizado
# =========================================================

CC        := gcc
NASM      := nasm
PYTHON    ?= python3

CFLAGS    := -std=gnu11 -Wall -Wextra -O2 -g
NASMFLAGS := -f elf64 -g -F dwarf
LDFLAGS   := -lm

SRC_DIR    := src
INC_DIR    := include
OBJ_DIR    := obj
BIN_DIR    := bin

ASM_SCALAR := asm/scalar/stats_scalar.asm
ASM_VECTOR := asm/vector/stats_vector.asm

DRIVER_OBJ := $(OBJ_DIR)/driver.o
SCALAR_OBJ := $(OBJ_DIR)/stats_scalar.o
VECTOR_OBJ := $(OBJ_DIR)/stats_vector.o

TEST_SCALAR_OBJ := $(OBJ_DIR)/test_sum_scalar.o
TEST_VECTOR_OBJ := $(OBJ_DIR)/test_sum_vector.o

.PHONY: all clean dirs run-scalar run-vector test-sum
.PHONY: generate-inputs generate-inputs-large test-input test-input-large

all: $(BIN_DIR)/norm_scalar $(BIN_DIR)/norm_vector

dirs:
	@mkdir -p $(OBJ_DIR) $(BIN_DIR) data

# Compilacion del programa principal
$(DRIVER_OBJ): $(SRC_DIR)/driver.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

# Ensamblado de los kernels
$(SCALAR_OBJ): $(ASM_SCALAR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

$(VECTOR_OBJ): $(ASM_VECTOR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

# Enlace de los normalizadores
$(BIN_DIR)/norm_scalar: $(DRIVER_OBJ) $(SCALAR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/norm_vector: $(DRIVER_OBJ) $(VECTOR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Ejecucion del programa principal
run-scalar: $(BIN_DIR)/norm_scalar
	./$(BIN_DIR)/norm_scalar data/input.dat data/output_scalar.dat 10

run-vector: $(BIN_DIR)/norm_vector
	./$(BIN_DIR)/norm_vector data/input.dat data/output_vector.dat 10

# Compilacion de las pruebas de sum_array
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

# Generacion y validacion de entradas independiente de NASM
generate-inputs:
	$(PYTHON) tools/gen_input.py --suite small --out-dir data/inputs --seed 123

generate-inputs-large:
	$(PYTHON) tools/gen_input.py --suite large --out-dir data/inputs --seed 123

test-input:
	$(PYTHON) tools/test_input.py

test-input-large:
	$(PYTHON) tools/test_input.py --large

# Limpieza de objetos y ejecutables
clean:
	rm -rf $(OBJ_DIR) $(BIN_DIR)

# Verificacion completa contra NumPy y entre implementaciones
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

.PHONY: test-integration
test-integration: all $(BIN_DIR)/test_kernels_scalar $(BIN_DIR)/test_kernels_vector
	$(PYTHON) tools/test_integration.py
