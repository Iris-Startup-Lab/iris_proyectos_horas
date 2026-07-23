#!/usr/bin/env bash
# ==============================================================================
# Script de ejecución del Pipeline Iris Proyectos Horas para Linux / macOS (Bash).
# Uso: ./run_pipeline.sh [FLAGS]
# Ejemplo: ./run_pipeline.sh --weeks 2
#          ./run_pipeline.sh --test
# ==============================================================================

set -e

ENV_NAME="data_engineering"

if command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)" 2>/dev/null || true
    conda activate "$ENV_NAME" 2>/dev/null || true
fi

if command -v python &> /dev/null; then
    PYTHON_BIN="python"
elif [ -f "$HOME/anaconda3/envs/$ENV_NAME/bin/python" ]; then
    PYTHON_BIN="$HOME/anaconda3/envs/$ENV_NAME/bin/python"
elif [ -f "$HOME/miniconda3/envs/$ENV_NAME/bin/python" ]; then
    PYTHON_BIN="$HOME/miniconda3/envs/$ENV_NAME/bin/python"
elif [ -f "/opt/anaconda3/envs/$ENV_NAME/bin/python" ]; then
    PYTHON_BIN="/opt/anaconda3/envs/$ENV_NAME/bin/python"
else
    echo "Error: No se encontró Python en el entorno '$ENV_NAME'." >&2
    exit 1
fi

echo "=== Ejecutando Pipeline Iris Proyectos Horas ($($PYTHON_BIN --version)) ==="
exec "$PYTHON_BIN" -m src.pipeline_actividades_trello "$@"
