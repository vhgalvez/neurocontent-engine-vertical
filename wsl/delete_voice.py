import argparse
import sys
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from voice_registry import delete_voice  # noqa: E402


def log(message: str) -> None:
    print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Elimina una voz del registry de forma consistente.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--voice-id", required=True, help="voice_id tecnico persistente a eliminar.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)

    try:
        runtime = get_runtime_paths()
        result = delete_voice(runtime, args.voice_id)
        log(
            "[delete_voice] OK "
            f"voice_id={result['voice_id']} "
            f"voice_name={result['voice_name']} "
            f"remaining_voices={result['remaining_voices']}"
        )
    except Exception as exc:
        log(f"[delete_voice] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
