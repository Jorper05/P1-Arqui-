#!/usr/bin/env bash
# Ejecuta el objetivo benchmark del Makefile desde la raiz del proyecto.
# Colocar este script en una carpeta situada directamente bajo la raiz,
# como tools/ o benchmark/, para que el cambio de directorio sea correcto.
#
# Parametros: todos los argumentos se pasan a make sin alterarlos.
# Permite asignaciones de variables y opciones de make, por ejemplo:
#   bash tools/run_benchmark.sh BENCH_SIZES="1000 100000" BENCH_REPS=30 SEED=123
# Ajustar la ruta del ejemplo a la ubicacion real del script.
# BENCH_RESULTS permite elegir el directorio de resultados.

# -e: termina ante un comando fallido, sujeto a las reglas de Bash.
# -u: rechaza el uso de variables no definidas.
# pipefail: hace fallar una tuberia si falla alguno de sus comandos.
set -euo pipefail

# BASH_SOURCE[0] identifica el script; dirname obtiene su carpeta.
# Cambia a la carpeta superior para ejecutar make desde la raiz,
# independientemente del directorio desde el que se invoco el script.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# make construye las dependencias de benchmark y ejecuta tools/measure.py.
# El objetivo verifica la correccion antes de medir y guarda muestras,
# metadatos, resumenes y grafico en el directorio configurado.
# "$@" conserva cada argumento y sus espacios como un parametro separado.
make benchmark "$@"
