#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-all}"

cd "$PROJECT_DIR"

case "$MODE" in
  all)
    bash wsl/run_audio.sh
    bash wsl/run_subs.sh
    ;;
  audio)
    bash wsl/run_audio.sh
    ;;
  subs)
    bash wsl/run_subs.sh
    ;;
  *)
    echo "Modo no valido: $MODE"
    echo "Usa: all | audio | subs"
    exit 1
    ;;
esac

echo "Pipeline WSL2 completado en modo: $MODE"
