import argparse
import os
import random
import sys
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from job_paths import build_job_paths, ensure_job_structure  # noqa: E402
from voice_prompting import prepare_voice_design_instruct  # noqa: E402
from voice_registry import (  # noqa: E402
    assign_voice_to_job,
    generate_voice_id,
    get_voice,
    get_voice_by_name,
    register_voice,
    validate_voice_index,
    validate_voice_name,
)

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

DEFAULT_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_DESCRIPTION = os.getenv(
    "QWEN_TTS_VOICE_DESCRIPTION",
    "Voz femenina madura, seria, clara y profesional para narracion tipo podcast.",
)
DEFAULT_REFERENCE_TEXT = os.getenv(
    "QWEN_TTS_REFERENCE_TEXT",
    "Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores.",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_REFERENCE_LANGUAGE", os.getenv("QWEN_TTS_LANGUAGE", "Spanish"))
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"


def log(message: str) -> None:
    print(message, flush=True)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def resolve_model_path(base_path: str) -> str:
    base = Path(base_path)
    if (base / "config.json").exists():
        return str(base)
    snapshots = sorted((base / "snapshots").iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            return str(snapshot)
    raise RuntimeError(f"No se encontro snapshot valido con config.json en {base}")


def get_device_and_dtype(device_mode: str) -> tuple[str, torch.dtype]:
    if device_mode == "cpu":
        return "cpu", torch.float32
    if device_mode == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible")
        return "cuda:0", torch.bfloat16
    return ("cuda:0", torch.bfloat16) if torch.cuda.is_available() else ("cpu", torch.float32)


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)


def load_model(model_path: str, device_mode: str, use_flash_attn: bool):
    resolved_model_path = resolve_model_path(model_path)
    device_map, dtype = get_device_and_dtype(device_mode)
    kwargs = {
        "device_map": device_map,
        "dtype": dtype,
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if use_flash_attn and str(device_map).startswith("cuda"):
        kwargs["attn_implementation"] = "flash_attention_2"
    model = Qwen3TTSModel.from_pretrained(resolved_model_path, **kwargs)
    if getattr(model.model, "tts_model_type", None) != "voice_design":
        raise RuntimeError("El modelo cargado no es VoiceDesign.")
    return model, resolved_model_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diseña y registra una voz con Qwen3-TTS VoiceDesign.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--scope", choices=["global", "job"], default="global")
    parser.add_argument("--job-id", help="Obligatorio cuando scope=job.")
    parser.add_argument("--voice-id", help="Permite forzar un voice_id concreto.")
    parser.add_argument(
        "--voice-name",
        default="voz_principal",
        help="Nombre logico de la voz. Debe ser unico y no parecer un voice_id interno.",
    )
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION, help="Descripcion natural de la voz.")
    parser.add_argument("--reference-text", default=DEFAULT_REFERENCE_TEXT, help="Texto corto para la referencia.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--assign-to-job", action="store_true", help="Asigna la voz al job si scope=job.")
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    parser.add_argument("--verbose-voice-debug", action="store_true", help="Imprime diagnostico detallado de registry y rutas.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        description = normalize_text(args.description)
        reference_text = normalize_text(args.reference_text)
        if args.scope == "job" and not args.job_id:
            raise RuntimeError("job_id es obligatorio cuando scope=job")
        if not description or not reference_text:
            raise RuntimeError("description y reference_text no pueden estar vacios")
        prompt_plan = prepare_voice_design_instruct(description)
        effective_instruct = prompt_plan["effective_instruct"]
        prompt_analysis = prompt_plan["analysis"]

        runtime = get_runtime_paths()
        normalized_voice_name = normalize_text(args.voice_name).replace(" ", "_")
        provisional_voice_id = args.voice_id or generate_voice_id(runtime, scope=args.scope, job_id=args.job_id)
        existing_by_name = get_voice_by_name(runtime, normalized_voice_name)
        existing_by_id = get_voice(runtime, provisional_voice_id)
        validate_voice_name(runtime, normalized_voice_name, current_voice_id=provisional_voice_id)

        if args.verbose_voice_debug:
            voice_index = runtime.voices_index_file.read_text(encoding="utf-8") if runtime.voices_index_file.exists() else "<missing>"
            log(f"[design_voice] runtime.dataset_root={runtime.dataset_root}")
            log(f"[design_voice] runtime.jobs_root={runtime.jobs_root}")
            log(f"[design_voice] runtime.voices_root={runtime.voices_root}")
            log(f"[design_voice] runtime.voices_index_file={runtime.voices_index_file}")
            log(f"[design_voice] provisional_voice_id={provisional_voice_id}")
            log(f"[design_voice] existing_by_name={existing_by_name}")
            log(f"[design_voice] existing_by_id={existing_by_id}")
            log(f"[design_voice] voices_index_snapshot={voice_index}")

        set_global_seed(args.seed)
        model, resolved_model_path = load_model(args.model_path, args.device, args.use_flash_attn)
        generator = getattr(model, "generate_voice_design", None)
        if not callable(generator):
            raise RuntimeError("La libreria qwen_tts no expone generate_voice_design()")

        wavs, sample_rate = generator(
            text=reference_text,
            instruct=effective_instruct,
            language=args.language,
            non_streaming_mode=True,
        )
        if not wavs:
            raise RuntimeError("generate_voice_design() no devolvio audio")

        voice_dir = runtime.voices_root / provisional_voice_id
        voice_dir.mkdir(parents=True, exist_ok=True)
        reference_wav = voice_dir / "reference.wav"
        reference_txt = voice_dir / "reference.txt"
        sf.write(str(reference_wav), wavs[0], sample_rate)
        reference_txt.write_text(reference_text + "\n", encoding="utf-8")

        record = register_voice(
            runtime,
            scope=args.scope,
            job_id=args.job_id,
            voice_name=normalized_voice_name,
            voice_description=description,
            model_name=resolved_model_path,
            language=args.language,
            seed=args.seed,
            voice_instruct=effective_instruct,
            reference_file=str(reference_wav),
            reference_text_file=str(reference_txt),
            engine="voice_design",
            voice_mode="design_only",
            tts_strategy_default="description_seed_preset",
            supports_reference_conditioning=False,
            supports_clone_prompt=False,
            voice_id=provisional_voice_id,
            notes=(
                "Referencia generada con Qwen3-TTS VoiceDesign. "
                "Esta voz queda registrada como design_only: reference.wav es un artefacto "
                "de referencia y trazabilidad, no una garantia de condicionamiento acustico "
                "directo en flujos posteriores."
            ),
        )

        if args.assign_to_job and args.job_id:
            job_paths = ensure_job_structure(build_job_paths(args.job_id, runtime))
            assign_voice_to_job(job_paths, record, selection_mode="manual")

        log(f"[design_voice] voice_id={record['voice_id']}")
        log("[design_voice] voice_mode=design_only strategy_default=description_seed_preset")
        log(
            "[design_voice] Prompt profile: "
            f"risk={prompt_analysis['risk']} "
            f"words={prompt_analysis['word_count']} "
            f"negations={prompt_analysis['negation_count']}"
        )
        if prompt_analysis["issues"]:
            log(f"[design_voice] Prompt issues: {', '.join(prompt_analysis['issues'])}")
        log(
            "[design_voice] Nota: design_only reutiliza voice_instruct + seed en cada clip. "
            "reference.wav queda como trazabilidad y muestra de referencia, pero no se usa como "
            "condicionamiento acustico directo en runtime."
        )
        if args.verbose_voice_debug:
            log(f"[design_voice] Effective voice_instruct: {effective_instruct}")
        log(f"[design_voice] Referencia guardada en {reference_wav}")

    except Exception as exc:
        log(f"[design_voice] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
