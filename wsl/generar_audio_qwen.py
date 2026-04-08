import argparse
import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    load_job_document,
    normalize_voice_record,
    register_voice,
    resolve_voice_selection,
    resolve_voice_runtime_strategy,
    resolve_tts_strategy_default,
    resolve_voice_mode,
    safe_read_json,
    update_job_audio_synthesis,
    update_job_artifact,
    validate_voice_index,
)

os.environ["ORT_LOGGING_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

DEFAULT_MODEL_PATH = os.getenv(
    "QWEN_TTS_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign",
)
DEFAULT_BASE_MODEL_PATH = os.getenv(
    "QWEN_TTS_BASE_MODEL_PATH",
    "/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base",
)
DEFAULT_LANGUAGE = os.getenv("QWEN_TTS_LANGUAGE", "Spanish")
DEFAULT_OVERWRITE = os.getenv("QWEN_TTS_OVERWRITE", "false").lower() == "true"
DEFAULT_DEVICE = os.getenv("QWEN_TTS_DEVICE", "auto").lower()
DEFAULT_TEST_SHORT = os.getenv("QWEN_TTS_TEST_SHORT", "false").lower() == "true"
DEFAULT_USE_FLASH_ATTN = os.getenv("QWEN_TTS_USE_FLASH_ATTN", "false").lower() == "true"
DEFAULT_VOICE_PRESET = os.getenv("QWEN_TTS_VOICE_PRESET", "mujer_podcast_seria_35_45")
DEFAULT_VOICE_SEED = int(os.getenv("QWEN_TTS_SEED", "424242"))
DEFAULT_TEST_TEXT = os.getenv("QWEN_TTS_TEST_TEXT", "Probando sistema de audio con Qwen3 TTS.")

VOICE_PRESETS = {
    "mujer_podcast_seria_35_45": {
        "identity": "Voz femenina madura de 35 a 45 años, seria, profesional y creible.",
        "style": "Ritmo medio, diccion clara, tono podcast profesional y estable.",
    },
    "mujer_documental_neutra": {
        "identity": "Voz femenina adulta, neutra, profesional y serena.",
        "style": "Ritmo medio-lento, lectura documental clara y natural.",
    },
    "hombre_narrador_sobrio": {
        "identity": "Voz masculina adulta, sobria, madura y segura.",
        "style": "Ritmo medio, diccion clara, tono serio pero cercano.",
    },
}


def log(message: str) -> None:
    print(message, flush=True)


def resolve_model_path(base_path: str) -> str:
    base = Path(base_path)
    if not base.exists():
        raise RuntimeError(f"No existe la ruta base del modelo: {base}")
    if (base / "config.json").exists():
        return str(base)
    snapshots_dir = base / "snapshots"
    snapshots = sorted(
        (path for path in snapshots_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for snapshot in snapshots:
        if (snapshot / "config.json").exists():
            return str(snapshot)
    raise RuntimeError(f"No se encontro snapshot valido con config.json en: {snapshots_dir}")


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


def resolve_generate_voice_design_method(model) -> callable:
    method = getattr(model, "generate_voice_design", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts instalada no expone generate_voice_design().")
    return method


def resolve_generate_voice_clone_method(model) -> callable:
    method = getattr(model, "generate_voice_clone", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts instalada no expone generate_voice_clone().")
    return method


def resolve_create_voice_clone_prompt_method(model) -> callable:
    method = getattr(model, "create_voice_clone_prompt", None)
    if not callable(method):
        raise RuntimeError("La libreria qwen_tts instalada no expone create_voice_clone_prompt().")
    return method


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


def load_prompt_json(path: Path) -> list[VoiceClonePromptItem]:
    payload = safe_read_json(path, default=None)
    if not payload or payload.get("format") != "qwen3_voice_clone_prompt_items":
        raise RuntimeError(f"Formato de prompt no soportado en {path}")
    return deserialize_prompt_items(payload.get("items", []))


def iter_job_ids(job_ids: list[str] | None) -> list[str]:
    runtime = get_runtime_paths()
    if job_ids:
        return job_ids
    if not runtime.jobs_root.exists():
        return []
    return sorted(path.name for path in runtime.jobs_root.iterdir() if path.is_dir())


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def read_text_file(path_value: str | None) -> str:
    candidate = Path(str(path_value or "").strip())
    if not candidate.exists():
        return ""
    return normalize_text(candidate.read_text(encoding="utf-8"))


def read_job_script_text(job_paths) -> str:
    script_path = job_paths.script if job_paths.script.exists() else job_paths.legacy_script_candidates[0]
    payload = safe_read_json(script_path, default={}) or {}
    return normalize_text(payload.get("guion_narrado", ""))


def resolve_requested_strategy(record: dict[str, Any]) -> str:
    return resolve_tts_strategy_default(record)


def build_synthesis_trace(
    *,
    requested: str,
    used: str,
    fallback_used: bool,
    fallback_reason: str = "",
    engine_used: str = "",
    reference_conditioning_used: bool = False,
    clone_prompt_used: bool = False,
    voice_preset_used: str = "",
    voice_instruct_source: str = "",
    seed_source: str = "",
    preset_source: str = "",
    runtime_source: str = "voice_registry.resolve_voice_runtime_strategy",
    runtime_model: str = "",
    identity_consistency_mode: str = "",
    identity_consistency_note: str = "",
    reference_runtime_used: bool = False,
) -> dict[str, Any]:
    return {
        "requested": requested,
        "used": used,
        "fallback_used": bool(fallback_used),
        "fallback_reason": fallback_reason,
        "engine_used": engine_used,
        "reference_conditioning_used": bool(reference_conditioning_used),
        "clone_prompt_used": bool(clone_prompt_used),
        "voice_preset_used": voice_preset_used,
        "voice_instruct_source": voice_instruct_source,
        "seed_source": seed_source,
        "preset_source": preset_source,
        "runtime_source": runtime_source,
        "runtime_model": runtime_model,
        "identity_consistency_mode": identity_consistency_mode,
        "identity_consistency_note": identity_consistency_note,
        "reference_runtime_used": bool(reference_runtime_used),
    }


def build_voice_instruction(preset_name: str, seed: int, description: str = "", identity: str = "", style: str = "") -> tuple[str, str, int]:
    preset = VOICE_PRESETS.get(preset_name)
    if not preset:
        valid = ", ".join(sorted(VOICE_PRESETS))
        raise RuntimeError(f"Preset de voz no valido: {preset_name}. Disponibles: {valid}")
    final_identity = normalize_text(identity or preset["identity"])
    final_style = normalize_text(style or preset["style"])
    final_description = normalize_text(description)
    instruct = " ".join(
        part
        for part in [
            final_identity,
            final_style,
            final_description,
            "Mantener identidad vocal consistente, estable y natural.",
        ]
        if part
    ).strip()
    return preset_name, instruct, seed


def resolve_or_register_voice(job_paths, explicit_voice_id: str | None, explicit_voice_name: str | None, resolved_model_path: str, default_preset: str, default_seed: int, language: str):
    runtime = get_runtime_paths()
    assigned = resolve_voice_selection(
        runtime,
        job_paths=job_paths,
        explicit_voice_id=explicit_voice_id,
        explicit_voice_name=explicit_voice_name,
    )
    if assigned:
        record = normalize_voice_record(assigned["record"])
        return record, assigned["selection_mode"]

    legacy_config = safe_read_json(job_paths.legacy_voice_config, default={}) or {}
    preset = legacy_config.get("voice_preset", default_preset)
    seed = int(legacy_config.get("seed", default_seed))
    description = normalize_text(legacy_config.get("voice_description", ""))
    identity = normalize_text(legacy_config.get("identity", ""))
    style = normalize_text(legacy_config.get("style", ""))
    preset_name, instruct, resolved_seed = build_voice_instruction(
        preset_name=preset,
        seed=seed,
        description=description,
        identity=identity,
        style=style,
    )
    record = register_voice(
        runtime,
        scope="job",
        job_id=job_paths.job_id,
        voice_name=legacy_config.get("voice_name") or f"job_{job_paths.job_id}_voice",
        voice_description=description or f"VoiceDesign auto-registrada para job {job_paths.job_id}.",
        model_name=resolved_model_path,
        language=language,
        seed=resolved_seed,
        voice_instruct=instruct,
        voice_preset=preset_name,
        voice_mode="design_only",
        tts_strategy_default="legacy_preset_fallback",
        supports_reference_conditioning=False,
        supports_clone_prompt=False,
        engine="voice_design",
        notes="Auto-registrada desde el flujo VoiceDesign por compatibilidad.",
    )
    assign_voice_to_job(job_paths, record, selection_mode="job_auto_registered")
    return normalize_voice_record(record), "job_auto_registered"


def generate_audio_voice_design(model, text: str, instruct: str, language: str):
    generator = resolve_generate_voice_design_method(model)
    wavs, sample_rate = generator(
        text=text,
        instruct=instruct,
        language=language,
        non_streaming_mode=True,
    )
    if not wavs:
        raise RuntimeError("generate_voice_design() no devolvio audio")
    return wavs[0], sample_rate


def synthesize_voice_design_from_registry(model, text: str, language: str, record: dict[str, Any], default_seed: int):
    raw_instruct = normalize_text(record.get("voice_instruct", "") or record.get("voice_description", ""))
    if not raw_instruct:
        raise RuntimeError(
            f"La voz {record.get('voice_id', '')} no tiene voice_instruct ni voice_description para VoiceDesign."
        )
    prompt_plan = prepare_voice_design_instruct(raw_instruct)
    instruct = prompt_plan["effective_instruct"]
    resolved_seed = int(record.get("seed", default_seed))
    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio_voice_design(
        model=model,
        text=text,
        instruct=instruct,
        language=record.get("language") or language,
    )
    consistency = describe_voice_identity_consistency(record)
    return wav, sample_rate, build_synthesis_trace(
        requested=resolve_requested_strategy(record),
        used="voice_design_from_registry",
        fallback_used=False,
        engine_used="voice_design",
        reference_conditioning_used=False,
        clone_prompt_used=False,
        voice_preset_used=record.get("voice_preset", ""),
        voice_instruct_source=(
            "voice_record.voice_instruct_normalized"
            if record.get("voice_instruct")
            else "voice_record.voice_description_normalized"
        ),
        seed_source="voice_record.seed" if record.get("seed") is not None else "global_default_seed",
        preset_source="voice_record" if record.get("voice_preset") else "not_used",
        runtime_model="voice_design",
        identity_consistency_mode=consistency["identity_consistency_mode"],
        identity_consistency_note=(
            f"{consistency['identity_consistency_note']} "
            f"Prompt risk={prompt_plan['analysis']['risk']} "
            f"(words={prompt_plan['analysis']['word_count']}, "
            f"negations={prompt_plan['analysis']['negation_count']})."
        ),
        reference_runtime_used=consistency["reference_runtime_used"],
    )


def generate_audio_voice_clone(model, text: str, language: str, prompt_items: list[VoiceClonePromptItem]):
    generator = resolve_generate_voice_clone_method(model)
    wavs, sample_rate = generator(
        text=text,
        language=language,
        voice_clone_prompt=prompt_items,
        non_streaming_mode=True,
    )
    if not wavs:
        raise RuntimeError("generate_voice_clone() no devolvio audio")
    return wavs[0], sample_rate


def build_prompt_from_reference(model, reference_wav: Path, reference_text: str):
    create_prompt = resolve_create_voice_clone_prompt_method(model)
    if not reference_wav.exists():
        raise RuntimeError(f"No existe reference.wav: {reference_wav}")
    x_vector_only_mode = not bool(normalize_text(reference_text))
    return create_prompt(
        ref_audio=str(reference_wav),
        ref_text=normalize_text(reference_text) if not x_vector_only_mode else None,
        x_vector_only_mode=x_vector_only_mode,
    )


def synthesize_description_seed_preset(model, text: str, language: str, record: dict[str, Any], default_preset: str, default_seed: int):
    preset_name, instruct, resolved_seed = build_voice_instruction(
        preset_name=record.get("voice_preset") or default_preset,
        seed=int(record.get("seed", default_seed)),
        description=record.get("voice_description", ""),
    )
    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio_voice_design(model=model, text=text, instruct=instruct, language=language)
    consistency = describe_voice_identity_consistency(
        record,
        {
            "voice_strategy": "legacy_preset_fallback",
            "runtime_model": "voice_design",
            "voice_mode": record.get("voice_mode", ""),
            "tts_strategy_default": resolve_requested_strategy(record),
        },
    )
    return wav, sample_rate, build_synthesis_trace(
        requested=resolve_requested_strategy(record),
        used="description_seed_preset",
        fallback_used=False,
        engine_used="voice_design",
        reference_conditioning_used=False,
        clone_prompt_used=False,
        voice_preset_used=preset_name,
        voice_instruct_source="legacy_preset_builder",
        seed_source="voice_record.seed" if record.get("seed") is not None else "global_default_seed",
        preset_source="voice_record" if record.get("voice_preset") else "global_default",
        runtime_model="voice_design",
        identity_consistency_mode=consistency["identity_consistency_mode"],
        identity_consistency_note=consistency["identity_consistency_note"],
        reference_runtime_used=consistency["reference_runtime_used"],
    )


def synthesize_reference_conditioned(model, text: str, language: str, record: dict[str, Any]):
    reference_wav = Path(str(record.get("reference_file") or "").strip())
    reference_text = read_text_file(record.get("reference_text_file"))
    prompt_items = build_prompt_from_reference(model, reference_wav, reference_text)
    wav, sample_rate = generate_audio_voice_clone(model=model, text=text, language=language, prompt_items=prompt_items)
    consistency = describe_voice_identity_consistency(
        record,
        {
            "voice_strategy": "base_clone_from_reference",
            "runtime_model": "base",
            "voice_mode": record.get("voice_mode", ""),
            "tts_strategy_default": resolve_requested_strategy(record),
        },
    )
    return wav, sample_rate, build_synthesis_trace(
        requested=resolve_requested_strategy(record),
        used="reference_conditioned",
        fallback_used=False,
        engine_used="voice_clone",
        reference_conditioning_used=True,
        clone_prompt_used=False,
        voice_preset_used="",
        voice_instruct_source="not_used",
        seed_source="not_used",
        preset_source="not_used",
        runtime_model="base",
        identity_consistency_mode=consistency["identity_consistency_mode"],
        identity_consistency_note=consistency["identity_consistency_note"],
        reference_runtime_used=consistency["reference_runtime_used"],
    )


def synthesize_clone_prompt(model, text: str, language: str, record: dict[str, Any]):
    prompt_path = Path(str(record.get("voice_clone_prompt_path") or "").strip())
    if not prompt_path.exists():
        raise RuntimeError(f"No existe voice_clone_prompt_path: {prompt_path}")
    prompt_items = load_prompt_json(prompt_path)
    wav, sample_rate = generate_audio_voice_clone(model=model, text=text, language=language, prompt_items=prompt_items)
    consistency = describe_voice_identity_consistency(
        record,
        {
            "voice_strategy": "base_clone_from_prompt",
            "runtime_model": "base",
            "voice_mode": record.get("voice_mode", ""),
            "tts_strategy_default": resolve_requested_strategy(record),
        },
    )
    return wav, sample_rate, build_synthesis_trace(
        requested=resolve_requested_strategy(record),
        used="clone_prompt",
        fallback_used=False,
        engine_used="voice_clone",
        reference_conditioning_used=False,
        clone_prompt_used=True,
        voice_preset_used="",
        voice_instruct_source="not_used",
        seed_source="not_used",
        preset_source="not_used",
        runtime_model="base",
        identity_consistency_mode=consistency["identity_consistency_mode"],
        identity_consistency_note=consistency["identity_consistency_note"],
        reference_runtime_used=consistency["reference_runtime_used"],
    )


def write_wav(path: Path, wav: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), wav, sample_rate)


def log_strategy_summary(job_id: str, selection_mode: str, record: dict[str, Any], trace: dict[str, Any], *, verbose: bool = False) -> None:
    log(f"[{job_id}] Voice selection source: {selection_mode}")
    log(f"[{job_id}] Voice resolved: {record.get('voice_id', '')}")
    log(f"[{job_id}] Voice name: {record.get('voice_name', '')}")
    log(f"[{job_id}] Voice mode: {record.get('voice_mode', '')}")
    log(f"[{job_id}] Requested strategy: {trace['requested']}")
    log(f"[{job_id}] Effective runtime strategy: {trace['used']}")
    log(f"[{job_id}] Runtime model: {trace.get('runtime_model', '')}")
    log(f"[{job_id}] Fallback used: {str(bool(trace['fallback_used'])).lower()}")
    log(f"[{job_id}] Runtime source: {trace.get('runtime_source', 'unknown')}")
    log(f"[{job_id}] Voice instruct source: {trace.get('voice_instruct_source', 'unknown')}")
    log(f"[{job_id}] Seed source: {trace.get('seed_source', 'unknown')}")
    log(f"[{job_id}] Preset source: {trace.get('preset_source', 'unknown')}")
    log(f"[{job_id}] Identity consistency mode: {trace.get('identity_consistency_mode', 'unknown')}")
    log(f"[{job_id}] Reference reused in runtime: {str(bool(trace.get('reference_runtime_used', False))).lower()}")
    if trace.get("voice_preset_used"):
        preset_source = trace.get("preset_source", "unknown")
        log(f"[{job_id}] Preset used: {trace['voice_preset_used']} (source={preset_source})")
    if trace["fallback_used"]:
        log(f"[{job_id}] Fallback reason: {trace['fallback_reason']}")
    note = str(trace.get("identity_consistency_note", "") or "").strip()
    if note:
        log(f"[{job_id}] Identity consistency note: {note}")
    if verbose:
        log(f"[{job_id}] Voice debug record: {json.dumps(record, ensure_ascii=False, sort_keys=True)}")
        log(f"[{job_id}] Voice debug trace: {json.dumps(trace, ensure_ascii=False, sort_keys=True)}")


def synthesize_audio_for_record(
    *,
    text: str,
    language: str,
    record: dict[str, Any],
    default_preset: str,
    default_seed: int,
    voice_design_model,
    base_model,
) -> tuple[np.ndarray, int, dict[str, Any]]:
    requested = resolve_requested_strategy(record)
    runtime_strategy = resolve_voice_runtime_strategy(record)
    effective_strategy = runtime_strategy["voice_strategy"]

    if effective_strategy == "voice_design_from_registry":
        if voice_design_model is None:
            raise RuntimeError(
                "La voz existe y requiere VoiceDesign desde el registry, pero el modelo VoiceDesign no esta disponible."
            )
        return synthesize_voice_design_from_registry(
            voice_design_model,
            text,
            language,
            record,
            default_seed,
        )

    if effective_strategy == "legacy_preset_fallback":
        if voice_design_model is None:
            raise RuntimeError(
                "La voz requiere el flujo legacy de VoiceDesign, pero el modelo VoiceDesign no esta disponible."
            )
        wav, sample_rate, trace = synthesize_description_seed_preset(
            voice_design_model,
            text,
            language,
            record,
            default_preset,
            default_seed,
        )
        trace["used"] = "legacy_preset_fallback"
        trace["requested"] = requested
        return wav, sample_rate, trace

    if effective_strategy == "base_clone_from_prompt":
        if base_model is None:
            raise RuntimeError(
                "La voz existe y requiere clone_prompt, pero el modelo Base no esta disponible en este runtime."
            )
        return synthesize_clone_prompt(base_model, text, language, record)

    if effective_strategy == "base_clone_from_reference":
        if base_model is None:
            raise RuntimeError(
                "La voz existe y requiere reference_conditioned, pero el modelo Base no esta disponible en este runtime."
            )
        return synthesize_reference_conditioned(base_model, text, language, record)

    raise RuntimeError(
        "La voz existe, pero el runtime no pudo mapearla a una estrategia de sintesis compatible "
        f"(voice_id={record.get('voice_id', '')}, voice_mode={record.get('voice_mode', '')}, "
        f"tts_strategy_default={requested})."
    )


def determine_required_batch_models(
    *,
    runtime,
    job_ids: list[str],
    explicit_voice_id: str | None,
    explicit_voice_name: str | None,
) -> set[str]:
    required_models: set[str] = set()
    for job_id in job_ids:
        job_paths = ensure_job_structure(build_job_paths(job_id, runtime))
        assigned = resolve_voice_selection(
            runtime,
            job_paths=job_paths,
            explicit_voice_id=explicit_voice_id,
            explicit_voice_name=explicit_voice_name,
        )
        if not assigned:
            required_models.add("voice_design")
            continue
        runtime_strategy = resolve_voice_runtime_strategy(assigned["record"])
        required_models.add(runtime_strategy["runtime_model"])
    return required_models


def process_job(
    voice_design_model,
    voice_design_model_path: str,
    base_model,
    job_id: str,
    overwrite: bool,
    default_preset: str,
    default_seed: int,
    language: str,
    explicit_voice_id: str | None,
    explicit_voice_name: str | None,
    verbose_voice_debug: bool,
) -> None:
    job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
    if job_paths.audio.exists() and not overwrite:
        assigned = resolve_voice_selection(
            get_runtime_paths(),
            job_paths=job_paths,
            explicit_voice_id=explicit_voice_id,
            explicit_voice_name=explicit_voice_name,
        )
        record = normalize_voice_record(assigned["record"]) if assigned else {}
        if assigned and record:
            assign_voice_to_job(job_paths, record, selection_mode=assigned.get("selection_mode", ""))
        audio_synthesis = load_job_document(job_paths).get("audio_synthesis", {})
        update_status(
            job_paths.status,
            audio_generated=True,
            last_step="audio_skipped_existing",
            voice_id=record.get("voice_id", ""),
            voice_scope=record.get("scope", ""),
            voice_source=(assigned.get("selection_mode", "") if assigned else ""),
            voice_name=record.get("voice_name", ""),
            voice_selection_mode=assigned.get("selection_mode", "") if assigned else "",
            voice_model_name=record.get("model_name", ""),
            voice_reference_file=record.get("reference_file", "") or "",
            voice_mode=record.get("voice_mode", ""),
            tts_strategy_requested=audio_synthesis.get("tts_strategy_requested", ""),
            tts_strategy_used=audio_synthesis.get("tts_strategy_used", ""),
            tts_fallback_used=bool(audio_synthesis.get("tts_fallback_used", False)),
            tts_fallback_reason=audio_synthesis.get("tts_fallback_reason", ""),
            voice_instruct_source=audio_synthesis.get("voice_instruct_source", ""),
            seed_source=audio_synthesis.get("seed_source", ""),
            preset_source=audio_synthesis.get("preset_source", ""),
            runtime_source=audio_synthesis.get("runtime_source", ""),
            audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
        )
        return

    text = read_job_script_text(job_paths)
    if not text:
        update_status(job_paths.status, audio_generated=False, last_step="audio_missing_script")
        return

    record, selection_mode = resolve_or_register_voice(
        job_paths=job_paths,
        explicit_voice_id=explicit_voice_id,
        explicit_voice_name=explicit_voice_name,
        resolved_model_path=voice_design_model_path,
        default_preset=default_preset,
        default_seed=default_seed,
        language=language,
    )
    assign_voice_to_job(job_paths, record, selection_mode=selection_mode)
    wav, sample_rate, trace = synthesize_audio_for_record(
        text=text,
        language=language,
        record=record,
        default_preset=default_preset,
        default_seed=default_seed,
        voice_design_model=voice_design_model,
        base_model=base_model,
    )
    log_strategy_summary(job_paths.job_id, selection_mode, record, trace, verbose=verbose_voice_debug)
    write_wav(job_paths.audio, wav, sample_rate)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    update_job_artifact(
        job_paths,
        artifact_type="audio",
        file_path=get_runtime_paths().to_dataset_relative(job_paths.audio),
        generated_at=generated_at,
    )
    update_job_audio_synthesis(
        job_paths,
        voice_record=record,
        selection_mode=selection_mode,
        strategy_requested=trace["requested"],
        strategy_used=trace["used"],
        fallback_used=trace["fallback_used"],
        fallback_reason=trace["fallback_reason"],
        engine_used=trace["engine_used"],
        reference_conditioning_used=trace["reference_conditioning_used"],
        clone_prompt_used=trace["clone_prompt_used"],
        voice_preset_used=trace["voice_preset_used"],
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
        last_step=f"audio_generated_{trace['used']}",
        voice_id=record.get("voice_id", ""),
        voice_scope=record.get("scope", ""),
        voice_source=selection_mode,
        voice_name=record.get("voice_name", ""),
        voice_selection_mode=selection_mode,
        voice_model_name=record.get("model_name", ""),
        voice_reference_file=record.get("reference_file", "") or "",
        voice_mode=record.get("voice_mode", ""),
        tts_strategy_requested=trace["requested"],
        tts_strategy_used=trace["used"],
        tts_fallback_used=trace["fallback_used"],
        tts_fallback_reason=trace["fallback_reason"],
        voice_instruct_source=trace.get("voice_instruct_source", ""),
        seed_source=trace.get("seed_source", ""),
        preset_source=trace.get("preset_source", ""),
        runtime_source=trace.get("runtime_source", ""),
        audio_file=get_runtime_paths().to_dataset_relative(job_paths.audio),
        audio_generated_at=generated_at,
    )
    log(
        f"[{job_paths.job_id}] Audio generado en {job_paths.audio} "
        f"con voice_id={record.get('voice_id', '')}, voice_mode={record.get('voice_mode', '')}, "
        f"strategy={trace['used']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera audio por jobs usando VoiceDesign.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--job-id", action="append", dest="job_ids", help="Procesa un job especifico. Repetible.")
    parser.add_argument("--voice-id", help="Selecciona una voz ya registrada.")
    parser.add_argument("--voice-name", help="Selecciona una voz ya registrada por voice_name.")
    parser.add_argument("--text", help="Genera un clip directo sin leer jobs.")
    parser.add_argument("--output", help="Ruta de salida cuando se usa --text.")
    parser.add_argument("--preset", default=DEFAULT_VOICE_PRESET, help="Preset por defecto.")
    parser.add_argument("--seed", type=int, default=DEFAULT_VOICE_SEED, help="Seed por defecto.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Idioma para Qwen3-TTS.")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH, help="Ruta del modelo VoiceDesign.")
    parser.add_argument("--base-model-path", default=DEFAULT_BASE_MODEL_PATH, help="Ruta del modelo Base para clone/reference.")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=["auto", "cpu", "cuda"], help="Device.")
    parser.add_argument("--overwrite", action="store_true", default=DEFAULT_OVERWRITE, help="Sobrescribe audio.")
    parser.add_argument("--test-short", action="store_true", default=DEFAULT_TEST_SHORT, help="Prueba corta.")
    parser.add_argument("--test-text", default=DEFAULT_TEST_TEXT, help="Texto para --test-short.")
    parser.add_argument("--use-flash-attn", action="store_true", default=DEFAULT_USE_FLASH_ATTN)
    parser.add_argument("--verbose-voice-debug", action="store_true", help="Imprime resolucion detallada de voz y runtime.")
    return parser.parse_args()


def run_direct_text(model, text: str, output: Path, preset: str, seed: int, language: str) -> None:
    _, instruct, resolved_seed = build_voice_instruction(preset_name=preset, seed=seed)
    set_global_seed(resolved_seed)
    wav, sample_rate = generate_audio_voice_design(model=model, text=normalize_text(text), instruct=instruct, language=language)
    write_wav(output, wav, sample_rate)
    log(f"[audio] Clip directo generado en {output}")


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    validate_voice_index(get_runtime_paths())

    try:
        if args.test_short:
            voice_design_model, _ = load_model(
                model_path=args.model_path,
                device_mode=args.device,
                use_flash_attn=args.use_flash_attn,
                expected_tts_model_type="voice_design",
            )
            output = get_runtime_paths().jobs_root / "test_short.wav"
            run_direct_text(model=voice_design_model, text=args.test_text, output=output, preset=args.preset, seed=args.seed, language=args.language)
            return

        if args.text:
            voice_design_model, _ = load_model(
                model_path=args.model_path,
                device_mode=args.device,
                use_flash_attn=args.use_flash_attn,
                expected_tts_model_type="voice_design",
            )
            output = Path(args.output) if args.output else PROJECT_DIR / "outputs" / "voice_design_preview.wav"
            run_direct_text(model=voice_design_model, text=args.text, output=output, preset=args.preset, seed=args.seed, language=args.language)
            return

        job_ids = iter_job_ids(args.job_ids)
        if not job_ids:
            log("[audio] No hay jobs para procesar")
            return

        runtime = get_runtime_paths()
        required_models = determine_required_batch_models(
            runtime=runtime,
            job_ids=job_ids,
            explicit_voice_id=args.voice_id,
            explicit_voice_name=args.voice_name,
        )
        resolved_voice_design_model_path = resolve_model_path(args.model_path) if "voice_design" in required_models else ""
        log(
            "[audio] Model plan: "
            f"voice_design={'yes' if 'voice_design' in required_models else 'no'}, "
            f"base={'yes' if 'base' in required_models else 'no'}"
        )
        voice_design_model = None
        if "voice_design" in required_models:
            voice_design_model, _ = load_model(
                model_path=args.model_path,
                device_mode=args.device,
                use_flash_attn=args.use_flash_attn,
                expected_tts_model_type="voice_design",
            )
            log(f"[audio] VoiceDesign model disponible: {args.model_path}")

        base_model = None
        if "base" in required_models:
            try:
                base_model, _ = load_model(
                    model_path=args.base_model_path,
                    device_mode=args.device,
                    use_flash_attn=args.use_flash_attn,
                    expected_tts_model_type="base",
                )
                log(f"[audio] Base model disponible: {args.base_model_path}")
            except Exception as base_exc:
                log(f"[audio] Base model no disponible para clone/reference flow: {base_exc}")

        log(f"[audio] Jobs detectados: {job_ids}")
        had_job_errors = False
        for job_id in job_ids:
            try:
                process_job(
                    voice_design_model=voice_design_model,
                    voice_design_model_path=resolved_voice_design_model_path,
                    base_model=base_model,
                    job_id=job_id,
                    overwrite=args.overwrite,
                    default_preset=args.preset,
                    default_seed=args.seed,
                    language=args.language,
                    explicit_voice_id=args.voice_id,
                    explicit_voice_name=args.voice_name,
                    verbose_voice_debug=args.verbose_voice_debug,
                )
            except Exception as exc:
                had_job_errors = True
                job_paths = ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))
                log(f"[{job_id}] Error generando audio: {exc}")
                traceback.print_exc()
                update_status(job_paths.status, audio_generated=False, last_step="audio_error_voice_design")
        if had_job_errors:
            sys.exit(1)

    except Exception as exc:
        log(f"[audio] Fallo general: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
