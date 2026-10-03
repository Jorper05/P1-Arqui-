#!/usr/bin/env bash
# Ejecuta el objetivo perf del Makefile desde la raiz del proyecto.
# Este script debe estar en una carpeta directamente bajo la raiz,
# como tools/ o benchmark/, para que el cambio de directorio sea correcto.
#
# Parametros: todos los argumentos se pasan a make. Permite variables
# del Makefile y opciones de make, por ejemplo:
#   bash tools/run_perf.sh PERF_SIZES="1000 100000" PERF_REPS=30 PERF_RUNS=3
# Ajustar la ruta del ejemplo a la ubicacion real del script.
# PERF indica el ejecutable perf; PERF_RESULTS, el directorio de resultados.
# PERF_REPS es el minimo solicitado de repeticiones internas del kernel,
# ajustado por tamano y sujeto al limite de tools/measure.py.
# PERF_RUNS indica procesos independientes por version y tamano.
# PERF_FLAGS agrega argumentos a measure.py, no directamente a perf stat.

# -e: termina ante un comando fallido, sujeto a las reglas de Bash.
# -u: rechaza el uso de variables no definidas.
# pipefail: hace fallar una tuberia si falla alguno de sus comandos.
set -euo pipefail

# Localiza la carpeta del script mediante BASH_SOURCE[0] y cambia a su
# carpeta superior. Asi make se ejecuta desde la raiz del proyecto,
# independientemente del directorio desde el que se invoco el script.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Construye las dependencias de perf y ejecuta tools/measure.py en modo perf.
# Comprueba el acceso a eventos y la correccion antes de medir; conserva
# contadores, comandos, logs, metadatos y tablas de ambas versiones.
# perf stat mide el proceso completo, incluida E/S; repetir el kernel busca
# amortizar esos costes. El objetivo no modifica permisos del sistema.
# "$@" conserva cada argumento y sus espacios como un parametro separado.
make perf "$@"
