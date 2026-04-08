#!/usr/bin/env bash
# run_audio.sh

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

export QWEN_TTS_MODEL_PATH="${QWEN_TTS_MODEL_PATH:-/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign}"
export QWEN_TTS_BASE_MODEL_PATH="${QWEN_TTS_BASE_MODEL_PATH:-/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base}"
export QWEN_TTS_VOICE_PRESET="${QWEN_TTS_VOICE_PRESET:-mujer_podcast_seria_35_45}"
export QWEN_TTS_SEED="${QWEN_TTS_SEED:-424242}"
export QWEN_TTS_LANGUAGE="${QWEN_TTS_LANGUAGE:-Spanish}"
export QWEN_TTS_OVERWRITE="${QWEN_TTS_OVERWRITE:-false}"
export QWEN_TTS_DEVICE="${QWEN_TTS_DEVICE:-auto}"
export QWEN_TTS_TEST_SHORT="${QWEN_TTS_TEST_SHORT:-false}"
export QWEN_TTS_TEST_TEXT="${QWEN_TTS_TEST_TEXT:-Probando sistema de audio con Qwen3 TTS.}"
export QWEN_TTS_USE_FLASH_ATTN="${QWEN_TTS_USE_FLASH_ATTN:-false}"
export VIDEO_DATASET_ROOT="${VIDEO_DATASET_ROOT:-/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset}"
export VIDEO_JOBS_ROOT="${VIDEO_JOBS_ROOT:-$VIDEO_DATASET_ROOT/jobs}"
export VIDEO_DEFAULT_VOICE_ID="${VIDEO_DEFAULT_VOICE_ID:-}"
export PYTHONUNBUFFERED=1

echo "Proyecto: $PROJECT_DIR"
echo "Python usado: $QWEN_PYTHON"
echo "Modelo usado: $QWEN_TTS_MODEL_PATH"
echo "Modelo base clone/reference: $QWEN_TTS_BASE_MODEL_PATH"
echo "Device: $QWEN_TTS_DEVICE"
echo "[audio] Configured fallback preset (only used if no persistent voice is resolvable): $QWEN_TTS_VOICE_PRESET"
echo "[audio] Configured fallback seed (only used in legacy fallback paths): $QWEN_TTS_SEED"
echo "[audio] VIDEO_DEFAULT_VOICE_ID: ${VIDEO_DEFAULT_VOICE_ID:-<unset>}"
echo "Dataset root: $VIDEO_DATASET_ROOT"
echo "Jobs root: $VIDEO_JOBS_ROOT"

if [ ! -x "$QWEN_PYTHON" ]; then
    echo "ERROR: no existe Python ejecutable en $QWEN_PYTHON" >&2
    exit 1
fi

set +e
"$QWEN_PYTHON" -u "$PROJECT_DIR/wsl/generar_audio_qwen.py" "$@"
EXIT_CODE=$?
set -e

echo "Exit code: $EXIT_CODE"
exit "$EXIT_CODE"
