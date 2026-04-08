import argparse
import sys
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from voice_registry import (  # noqa: E402
    get_voice,
    get_voice_by_name,
    register_voice,
    validate_voice_index,
)
from wsl.generate_audio_from_prompt import (  # noqa: E402
    DEFAULT_BASE_MODEL_PATH,
    DEFAULT_DEVICE,
    DEFAULT_OVERWRITE,
    DEFAULT_USE_FLASH_ATTN,
    build_or_load_prompt,
    load_model,
    normalize_text,
)


def log(message: str) -> None:
    print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convierte una voz persistida a clone_prompt usando reference.wav/reference.txt."
    )
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--voice-id", help="voice_id existente.")
    parser.add_argument("--voice-name", help="voice_name existente.")
    parser.add_argument("--model-path", default=DEFAULT_BASE_MODEL_PATH, help="Ruta del modelo Base.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE)
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    parser.add_argument("--verbose-voice-debug", action="store_true", help="Imprime diagnostico ampliado.")
    return parser.parse_args()


def resolve_voice_record(args: argparse.Namespace) -> dict:
    runtime = get_runtime_paths()
    if args.voice_id:
        record = get_voice(runtime, args.voice_id)
        if not record:
            raise RuntimeError(f"No existe voice_id={args.voice_id} en el registry.")
        return record
    if args.voice_name:
        record = get_voice_by_name(runtime, args.voice_name)
        if not record:
            raise RuntimeError(f"No existe voice_name={args.voice_name} en el registry.")
        return record
    raise RuntimeError("Debes indicar --voice-id o --voice-name.")


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        record = resolve_voice_record(args)
        reference_wav = Path(str(record.get("reference_file") or "").strip())
        if not reference_wav.exists():
            raise RuntimeError(
                f"La voz {record.get('voice_id', '')} no tiene reference.wav reutilizable: {reference_wav}"
            )
        reference_text_file = Path(str(record.get("reference_text_file") or "").strip())
        reference_text = ""
        if reference_text_file.exists():
            reference_text = normalize_text(reference_text_file.read_text(encoding="utf-8"))

        voice_dir = get_runtime_paths().voices_root / str(record["voice_id"]).strip()
        prompt_output = voice_dir / "voice_clone_prompt.json"
        if prompt_output.exists() and not args.overwrite:
            raise RuntimeError(
                f"Ya existe {prompt_output}. Usa --overwrite para regenerar el clone prompt."
            )

        model, resolved_model_path = load_model(
            model_path=args.model_path,
            device_mode=args.device,
            use_flash_attn=args.use_flash_attn,
            expected_tts_model_type="base",
        )
        prompt_items, saved_prompt_path = build_or_load_prompt(
            model=model,
            reference_wav=reference_wav,
            reference_text=reference_text or None,
            x_vector_only_mode=not bool(reference_text),
            prompt_input=None,
            prompt_output=prompt_output,
            save_prompt=True,
        )
        if not prompt_items or not saved_prompt_path:
            raise RuntimeError("No se pudo generar ni guardar voice_clone_prompt.json")

        updated_record = register_voice(
            get_runtime_paths(),
            scope=record["scope"],
            job_id=record.get("job_id"),
            voice_name=record["voice_name"],
            voice_description=record.get("voice_description", ""),
            model_name=resolved_model_path,
            language=record.get("language", ""),
            seed=record.get("seed"),
            voice_instruct=record.get("voice_instruct", ""),
            reference_file=str(reference_wav),
            reference_text_file=str(reference_text_file) if reference_text_file.exists() else None,
            voice_clone_prompt_path=saved_prompt_path,
            voice_preset=record.get("voice_preset", ""),
            voice_mode="clone_prompt",
            tts_strategy_default="clone_prompt",
            supports_reference_conditioning=True,
            supports_clone_prompt=True,
            engine="voice_clone",
            status=record.get("status", "active"),
            voice_id=record["voice_id"],
            notes=(
                f"{record.get('notes', '').strip()} "
                "Promoted to clone_prompt desde reference.wav/reference.txt usando Base. "
                "A partir de ahora el batch puede reutilizar anclaje acustico fuerte."
            ).strip(),
        )

        log(f"[promote_voice] voice_id={updated_record['voice_id']}")
        log(f"[promote_voice] voice_name={updated_record['voice_name']}")
        log("[promote_voice] voice_mode=clone_prompt tts_strategy_default=clone_prompt")
        log(f"[promote_voice] reference_file={updated_record.get('reference_file', '')}")
        log(f"[promote_voice] voice_clone_prompt_path={updated_record.get('voice_clone_prompt_path', '')}")
        if args.verbose_voice_debug:
            log(f"[promote_voice] model={resolved_model_path}")
            log(f"[promote_voice] reference_text_present={str(bool(reference_text)).lower()}")

    except Exception as exc:
        log(f"[promote_voice] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
