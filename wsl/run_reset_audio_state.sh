#!/usr/bin/env bash
# wsl\run_reset_audio_state.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
VOICE_ENV_FILE="${VOICE_ENV_FILE:-$PROJECT_DIR/wsl/voices.env}"
DOTENV_FILE="${DOTENV_FILE:-$PROJECT_DIR/.env}"

load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        set -a
        # shellcheck disable=SC1090
        source "$env_file"
        set +a
    fi
}

cd "$PROJECT_DIR"

load_env_file "$DOTENV_FILE"
load_env_file "$VOICE_ENV_FILE"

export VIDEO_DATASET_ROOT="${VIDEO_DATASET_ROOT:-/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset}"
export VIDEO_JOBS_ROOT="${VIDEO_JOBS_ROOT:-$VIDEO_DATASET_ROOT/jobs}"
export PYTHONUNBUFFERED=1

HAS_CONFIRM=false
HAS_DRY_RUN=false
for arg in "$@"; do
    if [ "$arg" = "--confirm" ]; then
        HAS_CONFIRM=true
    fi
    if [ "$arg" = "--dry-run" ]; then
        HAS_DRY_RUN=true
    fi
done

if [ "$HAS_CONFIRM" = false ] && [ "$HAS_DRY_RUN" = false ]; then
    echo "ERROR: este reset requiere --confirm. Usa --dry-run para inspeccionar sin cambios." >&2
    exit 1
fi

echo "Proyecto: $PROJECT_DIR"
echo "Python usado: $QWEN_PYTHON"
echo "Dataset root: $VIDEO_DATASET_ROOT"
echo "Jobs root: $VIDEO_JOBS_ROOT"

if [ ! -x "$QWEN_PYTHON" ]; then
    echo "ERROR: no existe Python ejecutable en $QWEN_PYTHON" >&2
    exit 1
fi

set +e
"$QWEN_PYTHON" -u "$PROJECT_DIR/wsl/reset_audio_state.py" "$@"
EXIT_CODE=$?
set -e

echo "Exit code: $EXIT_CODE"
exit "$EXIT_CODE"
