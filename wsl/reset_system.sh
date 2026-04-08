#!/usr/bin/env bash
# Deprecated compatibility wrapper.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[reset_system] DEPRECATED: usa bash wsl/run_reset_audio_state.sh ..." >&2
exec "$SCRIPT_DIR/run_reset_audio_state.sh" "$@"
