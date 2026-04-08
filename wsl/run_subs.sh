#!/usr/bin/env bash
# wsl/run_subs.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python real donde WhisperX YA funciona
DEFAULT_WHISPERX_PYTHON="/home/victory/miniconda3/bin/python"

# Python que ejecuta el wrapper
WRAPPER_PYTHON="${WRAPPER_PYTHON:-python3}"

# Python real de WhisperX
WHISPERX_PYTHON="${WHISPERX_PYTHON:-$DEFAULT_WHISPERX_PYTHON}"
VIDEO_DATASET_ROOT="${VIDEO_DATASET_ROOT:-/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset}"
VIDEO_JOBS_ROOT="${VIDEO_JOBS_ROOT:-$VIDEO_DATASET_ROOT/jobs}"

cd "$PROJECT_DIR"

echo "Proyecto: $PROJECT_DIR"
echo "Wrapper python: $WRAPPER_PYTHON"
echo "WhisperX python: $WHISPERX_PYTHON"
echo "Dataset root: $VIDEO_DATASET_ROOT"
echo "Jobs root: $VIDEO_JOBS_ROOT"

unset PYTHONPATH || true

if ! command -v "$WRAPPER_PYTHON" >/dev/null 2>&1; then
  echo "ERROR: no existe WRAPPER_PYTHON=$WRAPPER_PYTHON"
  exit 1
fi

if [ ! -x "$WHISPERX_PYTHON" ]; then
  echo "ERROR: no existe el ejecutable de WhisperX en:"
  echo "  $WHISPERX_PYTHON"
  exit 1
fi

echo "Generando subtítulos por job..."
VIDEO_DATASET_ROOT="$VIDEO_DATASET_ROOT" VIDEO_JOBS_ROOT="$VIDEO_JOBS_ROOT" WHISPERX_PYTHON="$WHISPERX_PYTHON" "$WRAPPER_PYTHON" wsl/generar_subtitulos.py
