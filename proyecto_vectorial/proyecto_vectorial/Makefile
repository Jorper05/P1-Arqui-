# =========================================================
# Makefile - Proyecto: Normalizador estadistico vectorizado
# =========================================================

CC        := gcc
NASM      := nasm
CFLAGS    := -std=gnu11 -Wall -Wextra -O2 -g
NASMFLAGS := -f elf64 -g -F dwarf
LDFLAGS   := -lm

SRC_DIR    := src
INC_DIR    := include
ASM_SCALAR := asm/scalar/stats_scalar.asm
ASM_VECTOR := asm/vector/stats_vector.asm
OBJ_DIR    := obj
BIN_DIR    := bin

DRIVER_OBJ := $(OBJ_DIR)/driver.o
SCALAR_OBJ := $(OBJ_DIR)/stats_scalar.o
VECTOR_OBJ := $(OBJ_DIR)/stats_vector.o

.PHONY: all clean run-scalar run-vector dirs

all: dirs $(BIN_DIR)/norm_scalar $(BIN_DIR)/norm_vector

dirs:
	@mkdir -p $(OBJ_DIR) $(BIN_DIR) data

$(BIN_DIR)/norm_scalar: $(DRIVER_OBJ) $(SCALAR_OBJ)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/norm_vector: $(DRIVER_OBJ) $(VECTOR_OBJ)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(DRIVER_OBJ): $(SRC_DIR)/driver.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

$(SCALAR_OBJ): $(ASM_SCALAR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

$(VECTOR_OBJ): $(ASM_VECTOR) | dirs
	$(NASM) $(NASMFLAGS) $< -o $@

# Atajos de conveniencia (requieren haber generado data/input.dat)
run-scalar: $(BIN_DIR)/norm_scalar
	./$(BIN_DIR)/norm_scalar data/input.dat data/output_scalar.dat 10

run-vector: $(BIN_DIR)/norm_vector
	./$(BIN_DIR)/norm_vector data/input.dat data/output_vector.dat 10

clean:
	rm -rf $(OBJ_DIR) $(BIN_DIR)

# Fase 3 / persona 2: validar sum_array sin llamar a otros kernels.
PYTHON ?= python3
.PHONY: test-phase3

$(OBJ_DIR)/sum_probe_scalar.o: tests/sum_probe.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -I$(INC_DIR) -c $< -o $@

$(OBJ_DIR)/sum_probe_vector.o: tests/sum_probe.c $(INC_DIR)/stats.h | dirs
	$(CC) $(CFLAGS) -DTEST_VECTOR -I$(INC_DIR) -c $< -o $@

$(BIN_DIR)/sum_scalar: $(OBJ_DIR)/sum_probe_scalar.o $(SCALAR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/sum_vector: $(OBJ_DIR)/sum_probe_vector.o $(VECTOR_OBJ) | dirs
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

test-phase3: $(BIN_DIR)/sum_scalar $(BIN_DIR)/sum_vector $(BIN_DIR)/norm_scalar $(BIN_DIR)/norm_vector
	$(PYTHON) tools/test_sum_phase3.py
