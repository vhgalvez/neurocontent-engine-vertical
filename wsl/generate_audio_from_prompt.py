import argparse
import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from director import update_status  # noqa: E402
from job_paths import build_job_paths, ensure_job_structure  # noqa: E402
from voice_prompting import prepare_voice_design_instruct  # noqa: E402
from voice_registry import (  # noqa: E402
    assign_voice_to_job,
    describe_voice_identity_consistency,
    get_voice,
    get_voice_by_name,
    normalize_voice_record,
    register_voice,
    resolve_voice_selection,
    resolve_voice_runtime_strategy,
    safe_read_json,
    update_job_artifact,
    update_job_audio_synthesis,
    validate_voice_index,
)

DEFAULT_BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_BASE_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
)
DEFAULT_DESIGN_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
DEFAULT_REFERENCE_LANGUAGE = os.getenv("QWEN_TTS_REFERENCE_LANGUAGE", DEFAULT_LANGUAGE)
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"
DEFAULT_X_VECTOR_ONLY = os.getenv("QWEN_TTS_X_VECTOR_ONLY_MODE", "false").lower() == "true"
DEFAULT_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))


def log(message: str) -> None:
    print(message, flush=True)


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def safe_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


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


def load_model(model_path: str, device_mode: str, use_flash_attn: bool, expected_tts_model_type: str):
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
    if getattr(model.model, "tts_model_type", None) != expected_tts_model_type:
        raise RuntimeError(f"El modelo cargado no es {expected_tts_model_type}.")
    return model, resolved_model_path


def serialize_prompt_items(items: list[VoiceClonePromptItem]) -> list[dict]:
    return [
        {
            "ref_code": item.ref_code.detach().cpu().tolist() if item.ref_code is not None else None,
            "ref_spk_embedding": item.ref_spk_embedding.detach().cpu().tolist(),
            "x_vector_only_mode": bool(item.x_vector_only_mode),
            "icl_mode": bool(item.icl_mode),
            "ref_text": item.ref_text,
        }
        for item in items
    ]


def deserialize_prompt_items(data: list[dict]) -> list[VoiceClonePromptItem]:
    items: list[VoiceClonePromptItem] = []
    for row in data:
        items.append(
            VoiceClonePromptItem(
                ref_code=torch.tensor(row["ref_code"], dtype=torch.long) if row.get("ref_code") is not None else None,
                ref_spk_embedding=torch.tensor(row["ref_spk_embedding"], dtype=torch.float32),
                x_vector_only_mode=bool(row.get("x_vector_only_mode", False)),
                icl_mode=bool(row.get("icl_mode", False)),
                ref_text=row.get("ref_text"),
            )
        )
    return items


def save_prompt_json(path: Path, prompt_items: list[VoiceClonePromptItem], metadata: dict) -> None:
    safe_write_json(path, {"format": "qwen3_voice_clone_prompt_items", "items": serialize_prompt_items(prompt_items), "metadata": metadata})


def load_prompt_json(path: Path) -> list[VoiceClonePromptItem]:
    payload = safe_read_json(path, default=None)
    if not payload or payload.get("format") != "qwen3_voice_clone_prompt_items":
        raise RuntimeError(f"Formato de prompt no soportado en {path}")
    return deserialize_prompt_items(payload.get("items", []))


def read_job_text(job_paths) -> str:
    script_path = job_paths.script if job_paths.script.exists() else job_paths.legacy_script_candidates[0]
    script_data = safe_read_json(script_path, default={}) or {}
    return normalize_text(script_data.get("guion_narrado", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera audio desde voces persistidas o desde referencia directa.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--job-id", help="Job a procesar.")
    parser.add_argument("--voice-id", help="Selecciona una voz ya registrada por voice_id.")
    parser.add_argument("--voice-name", help="Selecciona una voz ya registrada por voice_name.")
    parser.add_argument("--text", help="Texto directo para sintetizar sin usar job.")
    parser.add_argument("--output", help="Ruta de salida para --text.")
    parser.add_argument("--reference-wav", help="Ruta explicita al wav de referencia.")
    parser.add_argument("--reference-text", help="Texto exacto del wav de referencia.")
    parser.add_argument("--voice-clone-prompt", help="JSON previamente serializado.")
    parser.add_argument("--save-prompt", action="store_true", help="Guarda el prompt serializado.")
    parser.add_argument("--prompt-output", help="Ruta explicita para guardar el prompt serializado.")
    parser.add_argument("--register-voice-name", default="voz_principal", help="Nombre logico para registrar una voz nueva desde --reference-wav.")
    parser.add_argument("--scope", choices=["global", "job"], default="global")
    parser.add_argument("--x-vector-only-mode", action="store_true", default=DEFAULT_X_VECTOR_ONLY)
    parser.add_argument("--language", default=DEFAULT_LANGUAGE)
    parser.add_argument("--reference-language", default=DEFAULT_REFERENCE_LANGUAGE)
    parser.add_argument("--model-path", default=DEFAULT_BASE_MODEL_PATH, help="Ruta del modelo Base.")
    parser.add_argument("--design-model-path", default=DEFAULT_DESIGN_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"])
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    parser.add_argument("--verbose-voice-debug", action="store_true", help="Imprime resolucion detallada de voz y runtime.")
    return parser.parse_args()


def build_or_load_prompt(model, reference_wav: Path, reference_text: str | None, x_vector_only_mode: bool, prompt_input: Path | None, prompt_output: Path | None, save_prompt: bool):
    if prompt_input:
        return load_prompt_json(prompt_input), str(prompt_input)

    create_prompt = getattr(model, "create_voice_clone_prompt", None)
    if not callable(create_prompt):
        raise RuntimeError("La libreria qwen_tts no expone create_voice_clone_prompt()")
    if not reference_wav.exists():
        raise RuntimeError(f"No existe reference.wav: {reference_wav}")
    if not x_vector_only_mode and not normalize_text(reference_text or ""):
        raise RuntimeError("reference_text es obligatorio cuando x_vector_only_mode=false")

    prompt_items = create_prompt(ref_audio=str(reference_wav), ref_text=reference_text, x_vector_only_mode=x_vector_only_mode)
    saved_path = None
    if save_prompt:
        if prompt_output is None:
            prompt_output = reference_wav.parent / "voice_clone_prompt.json"
        save_prompt_json(prompt_output, prompt_items, {"reference_wav": str(reference_wav), "reference_text": reference_text})
        saved_path = str(prompt_output)
    return prompt_items, saved_path


def resolve_selected_voice(job_paths, args: argparse.Namespace):
    runtime = get_runtime_paths()
    if args.voice_name and not args.voice_id and args.reference_wav:
        existing = get_voice_by_name(runtime, args.voice_name)
        if existing:
            return normalize_voice_record(existing), "manual_voice_name"
        return None, ""

    selected = resolve_voice_selection(
        runtime,
        job_paths=job_paths,
        explicit_voice_id=args.voice_id,
        explicit_voice_name=args.voice_name,
    )
    if selected:
        return normalize_voice_record(selected["record"]), selected["selection_mode"]
    return None, ""


def resolve_voice(job_paths, args: argparse.Namespace, resolved_base_model_path: str | None):
    runtime = get_runtime_paths()
    selected_record, selection_mode = resolve_selected_voice(job_paths, args)
    if selected_record:
        return selected_record, selection_mode, resolve_voice_runtime_strategy(selected_record)

    if args.reference_wav:
        record = register_voice(
            runtime,
            scope=args.scope if not args.job_id else "job",
            job_id=job_paths.job_id if args.job_id else None,
            voice_name=normalize_text(args.voice_name or args.register_voice_name).replace(" ", "_"),
            voice_description="Voice clone manual.",
            model_name=resolved_base_model_path or "",
            language=args.reference_language,
            seed=args.seed,
            voice_instruct="",
            reference_file=str(Path(args.reference_wav)),
            reference_text_file=None,
            voice_mode="reference_conditioned",
            tts_strategy_default="reference_conditioned",
            supports_reference_conditioning=True,
            supports_clone_prompt=False,
            engine="voice_clone",
            voice_id=args.voice_id,
            notes="Registrada desde generate_audio_from_prompt.",
        )
        if args.job_id:
            assign_voice_to_job(job_paths, record, selection_mode="manual")
        normalized_record = normalize_voice_record(record)
        return normalized_record, "manual_reference_wav", resolve_voice_runtime_strategy(normalized_record)

    if args.voice_id or args.voice_name:
        raise RuntimeError(
            "La voz solicitada no pudo resolverse en este flujo. "
            "Si la voz existe y es design_only, debe sintetizarse por VoiceDesign desde el registry; "
            "si es clone/reference, debe tener referencia o prompt reutilizable."
        )

    raise RuntimeError(
        "No hay una voz resoluble. Usa --voice-id, --voice-name o --reference-wav."
    )


def resolve_generate_voice_design_method(model):
    method = getattr(model, "generate_voice_design", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts no expone generate_voice_design()")
    return method


def synthesize_with_voice_design(model, *, text: str, record: dict, language: str, seed: int | None):
    generator = resolve_generate_voice_design_method(model)
    resolved_seed = int(record.get("seed", seed or DEFAULT_SEED))
    set_global_seed(resolved_seed)
    raw_instruct = normalize_text(record.get("voice_instruct") or record.get("voice_description") or "")
    if not raw_instruct:
        raise RuntimeError(
            f"La voz {record.get('voice_id', '')} no tiene voice_instruct ni voice_description para VoiceDesign."
        )
    prompt_plan = prepare_voice_design_instruct(raw_instruct)
    instruct = prompt_plan["effective_instruct"]
    wavs, sample_rate = generator(
        text=text,
        instruct=instruct,
        language=record.get("language") or language,
        non_streaming_mode=True,
    )
    if not wavs:
        raise RuntimeError("generate_voice_design() no devolvio audio")
    consistency = describe_voice_identity_consistency(record)
    trace = {
        "voice_instruct_source": (
            "voice_record.voice_instruct_normalized"
            if record.get("voice_instruct")
            else "voice_record.voice_description_normalized"
        ),
        "seed_source": "voice_record.seed" if record.get("seed") is not None else "global_default_seed",
        "preset_source": "voice_record" if record.get("voice_preset") else "not_used",
        "runtime_source": "voice_registry.resolve_voice_runtime_strategy",
        "identity_consistency_mode": consistency["identity_consistency_mode"],
        "identity_consistency_note": (
            f"{consistency['identity_consistency_note']} "
            f"Prompt risk={prompt_plan['analysis']['risk']} "
            f"(words={prompt_plan['analysis']['word_count']}, "
            f"negations={prompt_plan['analysis']['negation_count']})."
        ),
        "reference_runtime_used": consistency["reference_runtime_used"],
    }
    return wavs[0], sample_rate, trace


def log_runtime_summary(prefix: str, selection_mode: str, record: dict, *, strategy_requested: str, strategy_used: str, engine_used: str, runtime_model: str, trace: dict, verbose: bool = False):
    log(f"{prefix} Voice selection source: {selection_mode}")
    log(f"{prefix} Voice resolved: {record.get('voice_id', '')}")
    log(f"{prefix} Voice name: {record.get('voice_name', '')}")
    log(f"{prefix} Voice mode: {record.get('voice_mode', '')}")
    log(f"{prefix} Requested strategy: {strategy_requested}")
    log(f"{prefix} Effective runtime strategy: {strategy_used}")
    log(f"{prefix} Runtime model: {runtime_model}")
    log(f"{prefix} Engine used: {engine_used}")
    log(f"{prefix} Fallback used: false")
    log(f"{prefix} Runtime source: {trace.get('runtime_source', 'voice_registry.resolve_voice_runtime_strategy')}")
    log(f"{prefix} Voice instruct source: {trace.get('voice_instruct_source', 'unknown')}")
    log(f"{prefix} Seed source: {trace.get('seed_source', 'unknown')}")
    log(f"{prefix} Preset source: {trace.get('preset_source', 'unknown')}")
    log(f"{prefix} Identity consistency mode: {trace.get('identity_consistency_mode', 'unknown')}")
    log(f"{prefix} Reference reused in runtime: {str(bool(trace.get('reference_runtime_used', False))).lower()}")
    if trace.get("voice_preset_used"):
        log(f"{prefix} Preset used: {trace['voice_preset_used']} (source={trace.get('preset_source', 'unknown')})")
    note = str(trace.get("identity_consistency_note", "") or "").strip()
    if note:
        log(f"{prefix} Identity consistency note: {note}")
    if verbose:
        log(f"{prefix} Voice debug record: {json.dumps(record, ensure_ascii=False, sort_keys=True)}")
        log(f"{prefix} Voice debug trace: {json.dumps(trace, ensure_ascii=False, sort_keys=True)}")


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        if not args.job_id and not args.text:
            raise RuntimeError("Debes indicar --job-id o --text")

        if args.job_id:
            job_paths = ensure_job_structure(build_job_paths(args.job_id, get_runtime_paths()))
            text = read_job_text(job_paths)
            if not text:
                raise RuntimeError(f"{job_paths.script} no contiene guion_narrado")
            output_path = job_paths.audio
            if output_path.exists() and not args.overwrite:
                raise RuntimeError(f"Ya existe {output_path}. Usa --overwrite para regenerarlo.")
        else:
            job_paths = None
            text = normalize_text(args.text)
            output_path = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_runtime_preview.wav"

        resolved_base_model_path = resolve_model_path(args.model_path) if args.reference_wav else None
        record, selection_mode, runtime_strategy = resolve_voice(job_paths, args, resolved_base_model_path)

        if runtime_strategy["runtime_model"] == "voice_design":
            if args.voice_clone_prompt or args.save_prompt:
                raise RuntimeError(
                    "La voz existe, pero el runtime esta intentando operar con artefactos de clone/reference. "
                    f"Esta voz esta registrada como {record.get('voice_mode', '')} y debe usar el flujo VoiceDesign."
                )
            model, _ = load_model(args.design_model_path, args.device, args.use_flash_attn, expected_tts_model_type="voice_design")
            wav, sample_rate, trace = synthesize_with_voice_design(
                model,
                text=text,
                record=record,
                language=args.language,
                seed=args.seed,
            )
            saved_prompt_path = record.get("voice_clone_prompt_path")
            updated_record = record
            strategy_requested = runtime_strategy["tts_strategy_default"]
            strategy_used = runtime_strategy["voice_strategy"]
            engine_used = "voice_design"
            reference_conditioning_used = False
            clone_prompt_used = False
            trace["voice_preset_used"] = updated_record.get("voice_preset", "")
            runtime_model = "voice_design"
        else:
            model, _ = load_model(args.model_path, args.device, args.use_flash_attn, expected_tts_model_type="base")
            generate_clone = getattr(model, "generate_voice_clone", None)
            if not callable(generate_clone):
                raise RuntimeError("La libreria qwen_tts no expone generate_voice_clone()")

            reference_wav = Path(args.reference_wav or record.get("reference_file") or "")
            reference_text = args.reference_text
            if reference_text is None:
                reference_text = normalize_text(Path(record["reference_text_file"]).read_text(encoding="utf-8")) if record.get("reference_text_file") and Path(record["reference_text_file"]).exists() else None
            prompt_input = Path(args.voice_clone_prompt) if args.voice_clone_prompt else (
                Path(record["voice_clone_prompt_path"]) if record.get("voice_clone_prompt_path") else None
            )
            prompt_output = Path(args.prompt_output) if args.prompt_output else None

            prompt_items, saved_prompt_path = build_or_load_prompt(
                model=model,
                reference_wav=reference_wav,
                reference_text=reference_text,
                x_vector_only_mode=args.x_vector_only_mode,
                prompt_input=prompt_input,
                prompt_output=prompt_output,
                save_prompt=args.save_prompt,
            )

            wavs, sample_rate = generate_clone(
                text=text,
                language=args.language,
                voice_clone_prompt=prompt_items,
                non_streaming_mode=True,
            )
            if not wavs:
                raise RuntimeError("generate_voice_clone() no devolvio audio")
            wav = wavs[0]

            updated_record = register_voice(
                get_runtime_paths(),
                scope=record["scope"],
                job_id=record.get("job_id"),
                voice_name=record["voice_name"],
                voice_description=record["voice_description"],
                model_name=record["model_name"],
                language=record["language"],
                seed=record.get("seed"),
                voice_instruct=record.get("voice_instruct", ""),
                reference_file=str(reference_wav),
                reference_text_file=record.get("reference_text_file"),
                voice_clone_prompt_path=saved_prompt_path or record.get("voice_clone_prompt_path"),
                voice_mode="clone_prompt" if (saved_prompt_path or record.get("voice_clone_prompt_path")) else "reference_conditioned",
                tts_strategy_default="clone_prompt" if (saved_prompt_path or record.get("voice_clone_prompt_path")) else "reference_conditioned",
                supports_reference_conditioning=True,
                supports_clone_prompt=bool(saved_prompt_path or record.get("voice_clone_prompt_path")),
                engine="voice_clone",
                voice_id=record["voice_id"],
                notes=record.get("notes", ""),
            )
            strategy_requested = "clone_prompt" if updated_record.get("voice_clone_prompt_path") else "reference_conditioned"
            strategy_used = strategy_requested
            engine_used = "voice_clone"
            reference_conditioning_used = not bool(updated_record.get("voice_clone_prompt_path"))
            clone_prompt_used = bool(updated_record.get("voice_clone_prompt_path"))
            trace = {
                "voice_instruct_source": "not_used",
                "seed_source": "not_used",
                "preset_source": "not_used",
                "runtime_source": "voice_registry.resolve_voice_runtime_strategy",
                "voice_preset_used": "",
            }
            trace.update(
                describe_voice_identity_consistency(
                    updated_record,
                    {
                        "voice_strategy": strategy_used,
                        "runtime_model": "base",
                        "voice_mode": updated_record.get("voice_mode", ""),
                        "tts_strategy_default": strategy_requested,
                    },
                )
            )
            runtime_model = "base"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), wav, sample_rate)
        log(f"[voice_runtime] Audio final guardado en {output_path}")
        log_runtime_summary(
            "[voice_runtime]",
            selection_mode,
            updated_record,
            strategy_requested=strategy_requested,
            strategy_used=strategy_used,
            engine_used=engine_used,
            runtime_model=runtime_model,
            trace=trace,
            verbose=args.verbose_voice_debug,
        )
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        if job_paths:
            assign_voice_to_job(job_paths, updated_record, selection_mode=selection_mode)
            update_job_artifact(
                job_paths,
                artifact_type="audio",
                file_path=get_runtime_paths().to_dataset_relative(job_paths.audio),
                generated_at=generated_at,
            )
            update_job_audio_synthesis(
                job_paths,
                voice_record=updated_record,
                selection_mode=selection_mode,
                strategy_requested=strategy_requested,
                strategy_used=strategy_used,
                fallback_used=False,
                fallback_reason="",
                engine_used=engine_used,
                reference_conditioning_used=reference_conditioning_used,
                clone_prompt_used=clone_prompt_used,
                voice_preset_used=updated_record.get("voice_preset", ""),
                voice_instruct_source=trace.get("voice_instruct_source", ""),
                seed_source=trace.get("seed_source", ""),
                preset_source=trace.get("preset_source", ""),
                runtime_source=trace.get("runtime_source", ""),
                identity_consistency_mode=trace.get("identity_consistency_mode", ""),
                identity_consistency_note=trace.get("identity_consistency_note", ""),
                reference_runtime_used=trace.get("reference_runtime_used", False),
                generated_at=generated_at,
            )
            update_status(
                job_paths.status,
                audio_generated=True,
                last_step=f"audio_generated_{strategy_used}",
                voice_id=updated_record["voice_id"],
                voice_scope=updated_record["scope"],
                voice_source=selection_mode,
                voice_name=updated_record["voice_name"],
                voice_selection_mode=selection_mode,
                voice_model_name=updated_record["model_name"],
                voice_reference_file=updated_record.get("reference_file", "") or "",
                voice_mode=updated_record.get("voice_mode", ""),
                tts_strategy_requested=strategy_requested,
                tts_strategy_used=strategy_used,
                tts_fallback_used=False,
                tts_fallback_reason="",
                voice_instruct_source=trace.get("voice_instruct_source", ""),
                seed_source=trace.get("seed_source", ""),
                preset_source=trace.get("preset_source", ""),
                runtime_source=trace.get("runtime_source", ""),
                audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
                audio_generated_at=generated_at,
            )

    except Exception as exc:
        if args.job_id:
            job_paths = ensure_job_structure(build_job_paths(args.job_id, get_runtime_paths()))
            update_status(job_paths.status, audio_generated=False, last_step="audio_error_voice_runtime")
        log(f"[voice_runtime] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
