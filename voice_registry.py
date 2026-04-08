import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from job_paths import JobPaths, RuntimePaths, first_existing_path

DEFAULT_GLOBAL_VOICE_ID_ENV = "VIDEO_DEFAULT_VOICE_ID"
DEFAULT_VOICE_MODE = "design_only"
DEFAULT_TTS_STRATEGY = "description_seed_preset"
VOICE_MODES = {"design_only", "reference_conditioned", "clone_prompt", "clone_ready"}
TTS_STRATEGIES = {
    "description_seed_preset",
    "reference_conditioned",
    "clone_prompt",
    "legacy_preset_fallback",
}
RESERVED_VOICE_NAME_PATTERN = re.compile(r"^voice_(global|job)_.+$", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "si"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def resolve_voice_mode(record: dict[str, Any] | None) -> str:
    payload = record or {}
    candidate = str(payload.get("voice_mode", "")).strip().lower()
    if candidate in VOICE_MODES:
        return candidate
    if payload.get("voice_clone_prompt_path"):
        return "clone_prompt"
    if payload.get("engine") == "voice_clone":
        return "reference_conditioned"
    return DEFAULT_VOICE_MODE


def resolve_tts_strategy_default(record: dict[str, Any] | None) -> str:
    payload = record or {}
    candidate = str(payload.get("tts_strategy_default", "")).strip().lower()
    if candidate in TTS_STRATEGIES:
        return candidate
    voice_mode = resolve_voice_mode(payload)
    if voice_mode == "clone_prompt":
        return "clone_prompt"
    if voice_mode in {"reference_conditioned", "clone_ready"}:
        if payload.get("voice_clone_prompt_path"):
            return "clone_prompt"
        return "reference_conditioned"
    return DEFAULT_TTS_STRATEGY


def normalize_voice_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized["voice_mode"] = resolve_voice_mode(normalized)
    normalized["tts_strategy_default"] = resolve_tts_strategy_default(normalized)
    normalized["reference_text_file"] = normalized.get("reference_text_file")
    normalized["supports_reference_conditioning"] = _normalize_bool(
        normalized.get("supports_reference_conditioning"),
        default=normalized["voice_mode"] in {"reference_conditioned", "clone_prompt"},
    )
    normalized["supports_clone_prompt"] = _normalize_bool(
        normalized.get("supports_clone_prompt"),
        default=normalized["voice_mode"] == "clone_prompt" or bool(normalized.get("voice_clone_prompt_path")),
    )
    normalized["voice_preset"] = str(normalized.get("voice_preset", "") or "").strip()
    normalized["engine"] = str(normalized.get("engine", "") or "").strip()
    return normalized


def load_voice_index(runtime: RuntimePaths) -> dict[str, Any]:
    payload = safe_read_json(runtime.voices_index_file, default=None)
    if payload:
        payload.setdefault("registry_version", "1.0")
        payload.setdefault("voices", [])
        payload.setdefault("updated_at", "")
        payload["voices"] = [normalize_voice_record(record) for record in payload["voices"]]
        return payload
    return {"registry_version": "1.0", "voices": [], "updated_at": ""}


def save_voice_index(runtime: RuntimePaths, payload: dict[str, Any]) -> None:
    payload["updated_at"] = now_iso()
    safe_write_json(runtime.voices_index_file, payload)


def initialize_empty_voice_index(runtime: RuntimePaths) -> dict[str, Any]:
    payload = {"registry_version": "1.0", "voices": [], "updated_at": ""}
    save_voice_index(runtime, payload)
    return load_voice_index(runtime)


def _voice_record_path(runtime: RuntimePaths, voice_id: str) -> Path:
    return runtime.voices_root / voice_id / "voice.json"


def _normalize_voice_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _voice_name_key(value: Any) -> str:
    return _normalize_voice_name(value).casefold()


def _find_index_record_by_voice_name(
    runtime: RuntimePaths,
    voice_name: str,
    *,
    exclude_voice_id: str | None = None,
) -> dict[str, Any] | None:
    target = _voice_name_key(voice_name)
    if not target:
        return None
    for record in load_voice_index(runtime)["voices"]:
        record_voice_id = str(record.get("voice_id", "")).strip()
        if exclude_voice_id and record_voice_id == exclude_voice_id:
            continue
        if _voice_name_key(record.get("voice_name", "")) == target:
            return normalize_voice_record(record)
    return None


def _iter_voice_dirs(runtime: RuntimePaths):
    if not runtime.voices_root.exists():
        return
    for child in sorted(runtime.voices_root.iterdir(), key=lambda path: path.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".delete_tmp_"):
            continue
        yield child


def _find_disk_record_by_voice_name(
    runtime: RuntimePaths,
    voice_name: str,
    *,
    exclude_voice_id: str | None = None,
) -> dict[str, Any] | None:
    target = _voice_name_key(voice_name)
    if not target:
        return None
    for voice_dir in _iter_voice_dirs(runtime):
        voice_id = voice_dir.name
        if exclude_voice_id and voice_id == exclude_voice_id:
            continue
        file_record = safe_read_json(voice_dir / "voice.json", default=None)
        if not file_record:
            continue
        if _voice_name_key(file_record.get("voice_name", "")) == target:
            return normalize_voice_record(file_record)
    return None


def validate_voice_name(
    runtime: RuntimePaths,
    voice_name: str,
    *,
    current_voice_id: str | None = None,
) -> str:
    normalized_voice_name = _normalize_voice_name(voice_name)
    if not normalized_voice_name:
        raise ValueError("ERROR: voice_name no puede estar vacio")
    if RESERVED_VOICE_NAME_PATTERN.match(normalized_voice_name):
        raise ValueError(
            "ERROR: voice_name no puede parecer un voice_id interno del sistema "
            f"({normalized_voice_name})"
        )

    existing = _find_index_record_by_voice_name(
        runtime,
        normalized_voice_name,
        exclude_voice_id=current_voice_id,
    )
    if existing is None:
        existing = _find_disk_record_by_voice_name(
            runtime,
            normalized_voice_name,
            exclude_voice_id=current_voice_id,
        )
    if existing is not None:
        raise ValueError(
            "ERROR: ya existe una voz con ese nombre "
            f"(voice_name={normalized_voice_name}, voice_id={existing.get('voice_id', '')})"
        )
    return normalized_voice_name


def get_voice(runtime: RuntimePaths, voice_id: str) -> dict[str, Any] | None:
    for record in load_voice_index(runtime)["voices"]:
        if record.get("voice_id") == voice_id:
            record_path = _voice_record_path(runtime, voice_id)
            file_record = safe_read_json(record_path, default=None)
            return normalize_voice_record(file_record or record)

    record_path = _voice_record_path(runtime, voice_id)
    payload = safe_read_json(record_path, default=None)
    return normalize_voice_record(payload) if payload else None


def get_voice_by_name(runtime: RuntimePaths, voice_name: str) -> dict[str, Any] | None:
    record = _find_index_record_by_voice_name(runtime, voice_name)
    if record is not None:
        return normalize_voice_record(record)
    record = _find_disk_record_by_voice_name(runtime, voice_name)
    return normalize_voice_record(record) if record is not None else None


def resolve_voice_runtime_strategy(record: dict[str, Any]) -> dict[str, str]:
    normalized = normalize_voice_record(record)
    voice_mode = normalized["voice_mode"]
    requested = resolve_tts_strategy_default(normalized)
    has_prompt = bool(str(normalized.get("voice_clone_prompt_path") or "").strip())
    has_reference = bool(str(normalized.get("reference_file") or "").strip())
    supports_reference = bool(normalized.get("supports_reference_conditioning"))
    supports_clone = bool(normalized.get("supports_clone_prompt"))

    if voice_mode == "design_only":
        strategy = "legacy_preset_fallback" if requested == "legacy_preset_fallback" else "voice_design_from_registry"
        return {
            "voice_mode": voice_mode,
            "tts_strategy_default": requested,
            "voice_strategy": strategy,
            "runtime_model": "voice_design",
        }

    if has_prompt or supports_clone or voice_mode in {"clone_prompt", "clone_ready"}:
        if has_prompt:
            return {
                "voice_mode": voice_mode,
                "tts_strategy_default": requested,
                "voice_strategy": "base_clone_from_prompt",
                "runtime_model": "base",
            }
        if has_reference or supports_reference:
            return {
                "voice_mode": voice_mode,
                "tts_strategy_default": requested,
                "voice_strategy": "base_clone_from_reference",
                "runtime_model": "base",
            }
        raise RuntimeError(
            "La voz existe, pero esta marcada como clone/reference sin prompt ni referencia reutilizable "
            f"(voice_id={normalized.get('voice_id', '')}, voice_mode={voice_mode})."
        )

    if has_reference or supports_reference or voice_mode == "reference_conditioned":
        return {
            "voice_mode": voice_mode,
            "tts_strategy_default": requested,
            "voice_strategy": "base_clone_from_reference",
            "runtime_model": "base",
        }

    if requested in {"description_seed_preset", "legacy_preset_fallback"}:
        strategy = "legacy_preset_fallback" if requested == "legacy_preset_fallback" else "voice_design_from_registry"
        return {
            "voice_mode": voice_mode,
            "tts_strategy_default": requested,
            "voice_strategy": strategy,
            "runtime_model": "voice_design",
        }

    raise RuntimeError(
        "La voz existe, pero no se pudo derivar una estrategia operativa valida desde el registry "
        f"(voice_id={normalized.get('voice_id', '')}, voice_mode={voice_mode}, "
        f"tts_strategy_default={requested})."
    )


def describe_voice_identity_consistency(
    record: dict[str, Any],
    runtime_strategy: dict[str, str] | None = None,
) -> dict[str, Any]:
    strategy = runtime_strategy or resolve_voice_runtime_strategy(record)
    effective = str(strategy.get("voice_strategy", "")).strip()

    if effective == "voice_design_from_registry":
        return {
            "identity_consistency_mode": "soft_prompt_conditioning_only",
            "identity_consistency_note": (
                "Esta voz usa VoiceDesign desde voice_instruct + seed + texto. "
                "reference.wav se conserva como trazabilidad, pero no se reutiliza como "
                "condicionamiento acustico en runtime. Puede haber drift de timbre, sexo "
                "aparente o energia entre clips. Para una identidad fuerte entre clips, "
                "hay que convertir esta voz a reference_conditioned o clone_prompt con Base."
            ),
            "reference_runtime_used": False,
        }

    if effective == "legacy_preset_fallback":
        return {
            "identity_consistency_mode": "legacy_soft_prompt_conditioning",
            "identity_consistency_note": (
                "El runtime esta usando VoiceDesign por preset/seed legacy. No hay anclaje "
                "acustico fuerte entre clips y la consistencia de identidad es la mas debil."
            ),
            "reference_runtime_used": False,
        }

    if effective == "base_clone_from_reference":
        return {
            "identity_consistency_mode": "reference_anchored_clone",
            "identity_consistency_note": (
                "El runtime Base reutiliza reference.wav y reference.txt en sintesis. Esta es "
                "la ruta con anclaje de identidad mas fuerte disponible en el sistema."
            ),
            "reference_runtime_used": True,
        }

    if effective == "base_clone_from_prompt":
        return {
            "identity_consistency_mode": "prompt_anchored_clone",
            "identity_consistency_note": (
                "El runtime Base reutiliza voice_clone_prompt persistido. No vuelve a leer "
                "reference.wav en cada clip, pero mantiene un anclaje acustico mucho mas "
                "fuerte que design_only."
            ),
            "reference_runtime_used": False,
        }

    return {
        "identity_consistency_mode": "unknown",
        "identity_consistency_note": (
            "No se pudo clasificar la fuerza de anclaje vocal para esta estrategia."
        ),
        "reference_runtime_used": False,
    }


def _next_voice_id(runtime: RuntimePaths, prefix: str) -> str:
    suffixes: list[int] = []
    for record in load_voice_index(runtime)["voices"]:
        voice_id = str(record.get("voice_id", ""))
        if voice_id.startswith(prefix):
            suffix = voice_id[len(prefix):]
            if suffix.isdigit():
                suffixes.append(int(suffix))
    return f"{prefix}{max(suffixes, default=0) + 1:04d}"


def generate_voice_id(runtime: RuntimePaths, scope: str, job_id: str | None = None) -> str:
    if scope == "global":
        return _next_voice_id(runtime, "voice_global_")
    if scope == "job":
        if not job_id:
            raise ValueError("job_id es obligatorio para voces scope=job.")
        return _next_voice_id(runtime, f"voice_job_{job_id}_")
    raise ValueError(f"Scope de voz no soportado: {scope}")


def upsert_voice(runtime: RuntimePaths, record: dict[str, Any]) -> dict[str, Any]:
    voice_id = str(record["voice_id"]).strip()
    if not voice_id:
        raise ValueError("voice_id es obligatorio.")
    voice_name = validate_voice_name(runtime, record.get("voice_name", voice_id), current_voice_id=voice_id)

    stored = normalize_voice_record({
        "voice_id": voice_id,
        "scope": record.get("scope", "global"),
        "job_id": record.get("job_id"),
        "voice_name": voice_name,
        "voice_description": record.get("voice_description", ""),
        "model_name": record.get("model_name", ""),
        "language": record.get("language", ""),
        "seed": record.get("seed"),
        "voice_instruct": record.get("voice_instruct", ""),
        "reference_file": record.get("reference_file"),
        "reference_text_file": record.get("reference_text_file"),
        "voice_clone_prompt_path": record.get("voice_clone_prompt_path"),
        "voice_preset": record.get("voice_preset", ""),
        "voice_mode": record.get("voice_mode"),
        "tts_strategy_default": record.get("tts_strategy_default"),
        "supports_reference_conditioning": record.get("supports_reference_conditioning"),
        "supports_clone_prompt": record.get("supports_clone_prompt"),
        "engine": record.get("engine", ""),
        "status": record.get("status", "active"),
        "notes": record.get("notes", ""),
        "created_at": record.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    })

    voice_dir = runtime.voices_root / voice_id
    voice_dir.mkdir(parents=True, exist_ok=True)
    safe_write_json(voice_dir / "voice.json", stored)

    index_payload = load_voice_index(runtime)
    voices = [row for row in index_payload["voices"] if row.get("voice_id") != voice_id]
    voices.append(stored)
    voices.sort(key=lambda row: str(row.get("voice_id", "")))
    index_payload["voices"] = voices
    save_voice_index(runtime, index_payload)
    return stored


def register_voice(
    runtime: RuntimePaths,
    *,
    scope: str,
    voice_name: str,
    voice_description: str,
    model_name: str,
    language: str,
    seed: int | None,
    voice_instruct: str,
    reference_file: str | None = None,
    reference_text_file: str | None = None,
    job_id: str | None = None,
    voice_clone_prompt_path: str | None = None,
    voice_preset: str = "",
    voice_mode: str | None = None,
    tts_strategy_default: str | None = None,
    supports_reference_conditioning: bool | None = None,
    supports_clone_prompt: bool | None = None,
    engine: str = "",
    status: str = "active",
    notes: str = "",
    voice_id: str | None = None,
) -> dict[str, Any]:
    final_voice_id = voice_id or generate_voice_id(runtime, scope=scope, job_id=job_id)
    existing = get_voice(runtime, final_voice_id)

    return upsert_voice(
        runtime,
        {
            "voice_id": final_voice_id,
            "scope": scope,
            "job_id": job_id,
            "voice_name": voice_name,
            "voice_description": voice_description,
            "model_name": model_name,
            "language": language,
            "seed": seed,
            "voice_instruct": voice_instruct,
            "reference_file": reference_file,
            "reference_text_file": reference_text_file,
            "voice_clone_prompt_path": voice_clone_prompt_path,
            "voice_preset": voice_preset,
            "voice_mode": voice_mode,
            "tts_strategy_default": tts_strategy_default,
            "supports_reference_conditioning": supports_reference_conditioning,
            "supports_clone_prompt": supports_clone_prompt,
            "engine": engine,
            "status": status,
            "notes": notes,
            "created_at": existing.get("created_at") if existing else None,
        },
    )


def load_job_document(job_paths: JobPaths) -> dict[str, Any]:
    current = safe_read_json(job_paths.job_file, default=None)
    if current:
        current.setdefault("job_id", job_paths.job_id)
        current.setdefault("job_schema_version", "2.0")
        current.setdefault("voice", {})
        current.setdefault("artifacts", {})
        current.setdefault("audio_synthesis", {})
        return current

    return {
        "job_id": job_paths.job_id,
        "job_schema_version": "2.0",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "voice": {},
        "artifacts": {},
        "audio_synthesis": {},
    }


def save_job_document(job_paths: JobPaths, document: dict[str, Any]) -> dict[str, Any]:
    document["updated_at"] = now_iso()
    safe_write_json(job_paths.job_file, document)
    return document


def assign_voice_to_job(
    job_paths: JobPaths,
    voice_record: dict[str, Any],
    *,
    selection_mode: str,
    notes: str = "",
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    document["voice"] = {
        "voice_id": voice_record.get("voice_id"),
        "scope": voice_record.get("scope"),
        "job_id": voice_record.get("job_id"),
        "voice_mode": voice_record.get("voice_mode"),
        "tts_strategy_default": voice_record.get("tts_strategy_default"),
        "voice_source": selection_mode,
        "selection_mode": selection_mode,
        "voice_name": voice_record.get("voice_name"),
        "voice_description": voice_record.get("voice_description"),
        "model_name": voice_record.get("model_name"),
        "language": voice_record.get("language"),
        "seed": voice_record.get("seed"),
        "voice_instruct": voice_record.get("voice_instruct"),
        "reference_file": voice_record.get("reference_file"),
        "reference_text_file": voice_record.get("reference_text_file"),
        "voice_clone_prompt_path": voice_record.get("voice_clone_prompt_path"),
        "supports_reference_conditioning": voice_record.get("supports_reference_conditioning"),
        "supports_clone_prompt": voice_record.get("supports_clone_prompt"),
        "voice_preset": voice_record.get("voice_preset", ""),
        "engine": voice_record.get("engine"),
        "status": voice_record.get("status"),
        "notes": notes,
        "assigned_at": now_iso(),
    }
    return save_job_document(job_paths, document)


def update_job_audio_synthesis(
    job_paths: JobPaths,
    *,
    voice_record: dict[str, Any],
    selection_mode: str,
    strategy_requested: str,
    strategy_used: str,
    fallback_used: bool,
    fallback_reason: str = "",
    engine_used: str = "",
    reference_conditioning_used: bool = False,
    clone_prompt_used: bool = False,
    voice_preset_used: str = "",
    voice_instruct_source: str = "",
    seed_source: str = "",
    preset_source: str = "",
    runtime_source: str = "",
    identity_consistency_mode: str = "",
    identity_consistency_note: str = "",
    reference_runtime_used: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    document["audio_synthesis"] = {
        "voice_id": voice_record.get("voice_id"),
        "voice_scope": voice_record.get("scope"),
        "voice_source": selection_mode,
        "voice_mode": voice_record.get("voice_mode"),
        "tts_strategy_requested": strategy_requested,
        "tts_strategy_used": strategy_used,
        "tts_fallback_used": bool(fallback_used),
        "tts_fallback_reason": fallback_reason,
        "engine_used": engine_used or voice_record.get("engine", ""),
        "reference_conditioning_used": bool(reference_conditioning_used),
        "clone_prompt_used": bool(clone_prompt_used),
        "voice_preset_used": voice_preset_used,
        "voice_instruct_source": voice_instruct_source,
        "seed_source": seed_source,
        "preset_source": preset_source,
        "runtime_source": runtime_source,
        "identity_consistency_mode": identity_consistency_mode,
        "identity_consistency_note": identity_consistency_note,
        "reference_runtime_used": bool(reference_runtime_used),
        "generated_at": generated_at or now_iso(),
    }
    return save_job_document(job_paths, document)


def update_job_artifact(
    job_paths: JobPaths,
    *,
    artifact_type: str,
    file_path: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    document = load_job_document(job_paths)
    artifacts = document.setdefault("artifacts", {})
    artifacts[artifact_type] = {
        "file": file_path,
        "generated_at": generated_at or now_iso(),
    }
    return save_job_document(job_paths, document)


def resolve_job_voice_assignment(
    runtime: RuntimePaths,
    job_paths: JobPaths,
    *,
    explicit_voice_id: str | None = None,
    explicit_voice_name: str | None = None,
) -> dict[str, Any] | None:
    if explicit_voice_id:
        record = get_voice(runtime, explicit_voice_id)
        if not record:
            raise RuntimeError(f"No existe voice_id={explicit_voice_id} en el registry.")
        return {"record": record, "selection_mode": "manual_voice_id"}

    if explicit_voice_name:
        record = get_voice_by_name(runtime, explicit_voice_name)
        if not record:
            raise RuntimeError(f"No existe voice_name={explicit_voice_name} en el registry.")
        return {"record": record, "selection_mode": "manual_voice_name"}

    job_document = load_job_document(job_paths)
    job_voice = job_document.get("voice") or {}
    voice_id = str(job_voice.get("voice_id", "")).strip()
    if voice_id:
        record = get_voice(runtime, voice_id)
        if record:
            return {
                "record": record,
                "selection_mode": job_voice.get("selection_mode", "job_assignment"),
            }

    default_global_voice_id = os.getenv(DEFAULT_GLOBAL_VOICE_ID_ENV, "").strip()
    if default_global_voice_id:
        record = get_voice(runtime, default_global_voice_id)
        if not record:
            raise RuntimeError(
                f"{DEFAULT_GLOBAL_VOICE_ID_ENV} apunta a una voz inexistente: {default_global_voice_id}"
            )
        return {"record": record, "selection_mode": "global_default"}

    return None


def resolve_voice_selection(
    runtime: RuntimePaths,
    *,
    job_paths: JobPaths | None = None,
    explicit_voice_id: str | None = None,
    explicit_voice_name: str | None = None,
) -> dict[str, Any] | None:
    if explicit_voice_id:
        record = get_voice(runtime, explicit_voice_id)
        if not record:
            raise RuntimeError(f"No existe voice_id={explicit_voice_id} en el registry.")
        return {"record": normalize_voice_record(record), "selection_mode": "manual_voice_id"}

    if explicit_voice_name:
        record = get_voice_by_name(runtime, explicit_voice_name)
        if not record:
            raise RuntimeError(f"No existe voice_name={explicit_voice_name} en el registry.")
        return {"record": normalize_voice_record(record), "selection_mode": "manual_voice_name"}

    if job_paths is not None:
        return resolve_job_voice_assignment(runtime, job_paths)

    default_global_voice_id = os.getenv(DEFAULT_GLOBAL_VOICE_ID_ENV, "").strip()
    if default_global_voice_id:
        record = get_voice(runtime, default_global_voice_id)
        if not record:
            raise RuntimeError(
                f"{DEFAULT_GLOBAL_VOICE_ID_ENV} apunta a una voz inexistente: {default_global_voice_id}"
            )
        return {"record": normalize_voice_record(record), "selection_mode": "global_default"}
    return None


def resolve_job_input_path(primary: Path, legacy_candidates: list[Path]) -> Path:
    return first_existing_path(primary, legacy_candidates)


def validate_voice_record(record: dict[str, Any]) -> None:
    normalized = normalize_voice_record(record)
    required_keys = {
        "voice_id",
        "scope",
        "voice_name",
        "voice_description",
        "model_name",
        "language",
        "voice_instruct",
        "status",
        "created_at",
        "updated_at",
    }
    missing = [key for key in sorted(required_keys) if key not in normalized]
    if missing:
        raise ValueError(f"Voice record invalido. Faltan claves: {', '.join(missing)}")
    if normalized["scope"] not in {"global", "job"}:
        raise ValueError(f"Scope de voz invalido: {normalized['scope']}")
    if not _normalize_voice_name(normalized["voice_name"]):
        raise ValueError("voice_name invalido: no puede estar vacio")
    if RESERVED_VOICE_NAME_PATTERN.match(normalized["voice_name"]):
        raise ValueError(
            "voice_name invalido: no puede parecer un voice_id interno "
            f"({normalized['voice_name']})"
        )
    if normalized["voice_mode"] not in VOICE_MODES:
        raise ValueError(f"voice_mode invalido: {normalized['voice_mode']}")
    if normalized["tts_strategy_default"] not in TTS_STRATEGIES:
        raise ValueError(f"tts_strategy_default invalido: {normalized['tts_strategy_default']}")


def validate_voice_index(runtime: RuntimePaths) -> None:
    payload = load_voice_index(runtime)
    if payload.get("registry_version") != "1.0":
        raise ValueError(f"registry_version no soportado: {payload.get('registry_version')}")
    seen_ids: set[str] = set()
    seen_names: dict[str, str] = {}
    for record in payload.get("voices", []):
        validate_voice_record(record)
        voice_id = str(record["voice_id"])
        if voice_id in seen_ids:
            raise ValueError(f"voice_id duplicado en registry: {voice_id}")
        seen_ids.add(voice_id)
        voice_name_key = _voice_name_key(record.get("voice_name", ""))
        existing_voice_id = seen_names.get(voice_name_key)
        if existing_voice_id is not None:
            raise ValueError(
                "voice_name duplicado en registry: "
                f"{record.get('voice_name', '')} "
                f"(voice_id={voice_id}, ya usado por voice_id={existing_voice_id})"
            )
        seen_names[voice_name_key] = voice_id

        voice_dir = runtime.voices_root / voice_id
        voice_file = voice_dir / "voice.json"
        if not voice_dir.exists():
            raise ValueError(f"Falta carpeta fisica para voice_id={voice_id}: {voice_dir}")
        if not voice_file.exists():
            raise ValueError(f"Falta voice.json para voice_id={voice_id}: {voice_file}")

        file_record = safe_read_json(voice_file, default=None)
        if not file_record:
            raise ValueError(f"voice.json vacio o invalido para voice_id={voice_id}: {voice_file}")
        file_voice_id = str(file_record.get("voice_id", "")).strip()
        if file_voice_id != voice_id:
            raise ValueError(
                f"voice.json inconsistente para {voice_id}: declara voice_id={file_voice_id}"
            )
        file_voice_name_key = _voice_name_key(file_record.get("voice_name", ""))
        if file_voice_name_key != voice_name_key:
            raise ValueError(
                "voice.json inconsistente con voices_index.json para "
                f"voice_id={voice_id}: voice_name index={record.get('voice_name', '')} "
                f"voice.json={file_record.get('voice_name', '')}"
            )


def find_voice_job_references(runtime: RuntimePaths, voice_id: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    if not runtime.jobs_root.exists():
        return references

    for job_dir in sorted((path for path in runtime.jobs_root.iterdir() if path.is_dir()), key=lambda path: path.name):
        job_file = job_dir / "job.json"
        if not job_file.exists():
            continue
        payload = safe_read_json(job_file, default={}) or {}
        job_voice_id = str((payload.get("voice") or {}).get("voice_id", "")).strip()
        if job_voice_id == voice_id:
            references.append({"job_id": job_dir.name, "location": "job.voice.voice_id"})
        audio_voice_id = str((payload.get("audio_synthesis") or {}).get("voice_id", "")).strip()
        if audio_voice_id == voice_id:
            references.append({"job_id": job_dir.name, "location": "job.audio_synthesis.voice_id"})
    return references


def delete_voice(runtime: RuntimePaths, voice_id: str) -> dict[str, Any]:
    normalized_voice_id = str(voice_id or "").strip()
    if not normalized_voice_id:
        raise ValueError("ERROR: voice_id es obligatorio para eliminar una voz")

    index_payload = load_voice_index(runtime)
    matching_records = [
        normalize_voice_record(record)
        for record in index_payload.get("voices", [])
        if str(record.get("voice_id", "")).strip() == normalized_voice_id
    ]
    if not matching_records:
        raise RuntimeError(f"ERROR: no existe voice_id={normalized_voice_id} en voices_index.json")
    if len(matching_records) != 1:
        raise RuntimeError(f"ERROR: voices_index.json es inconsistente para voice_id={normalized_voice_id}")

    record = matching_records[0]
    voice_dir = runtime.voices_root / normalized_voice_id
    voice_file = voice_dir / "voice.json"
    if not voice_dir.exists():
        raise RuntimeError(
            f"ERROR: no se puede eliminar {normalized_voice_id} porque falta su carpeta fisica: {voice_dir}"
        )
    if not voice_file.exists():
        raise RuntimeError(
            f"ERROR: no se puede eliminar {normalized_voice_id} porque falta voice.json: {voice_file}"
        )

    file_record = safe_read_json(voice_file, default=None)
    if not file_record:
        raise RuntimeError(f"ERROR: voice.json invalido para {normalized_voice_id}: {voice_file}")
    if str(file_record.get("voice_id", "")).strip() != normalized_voice_id:
        raise RuntimeError(
            "ERROR: voice.json no coincide con el directorio fisico de la voz "
            f"({normalized_voice_id})"
        )

    references = find_voice_job_references(runtime, normalized_voice_id)
    if references:
        jobs = ", ".join(f"{row['job_id']}:{row['location']}" for row in references)
        raise RuntimeError(
            f"ERROR: no se puede eliminar voice_id={normalized_voice_id} porque sigue referenciada en jobs: {jobs}"
        )

    backup_dir = runtime.voices_root / f".delete_tmp_{normalized_voice_id}"
    if backup_dir.exists():
        raise RuntimeError(
            f"ERROR: existe un directorio temporal de borrado pendiente: {backup_dir}"
        )

    remaining_records = [
        row
        for row in index_payload.get("voices", [])
        if str(row.get("voice_id", "")).strip() != normalized_voice_id
    ]
    original_updated_at = index_payload.get("updated_at", "")

    voice_dir.rename(backup_dir)
    try:
        updated_payload = {
            "registry_version": index_payload.get("registry_version", "1.0"),
            "voices": remaining_records,
            "updated_at": original_updated_at,
        }
        save_voice_index(runtime, updated_payload)
        validate_voice_index(runtime)
        shutil.rmtree(backup_dir)
    except Exception as exc:
        rollback_error: Exception | None = None
        try:
            index_payload["updated_at"] = original_updated_at
            save_voice_index(runtime, index_payload)
            if backup_dir.exists() and not voice_dir.exists():
                backup_dir.rename(voice_dir)
        except Exception as restore_exc:
            rollback_error = restore_exc

        if rollback_error is not None:
            raise RuntimeError(
                "ERROR: fallo eliminando la voz y tambien fallo el rollback. "
                f"Error original: {exc}. Error rollback: {rollback_error}"
            ) from exc
        raise RuntimeError(
            f"ERROR: fallo eliminando la voz {normalized_voice_id}. Se hizo rollback automatico. Detalle: {exc}"
        ) from exc

    return {
        "voice_id": normalized_voice_id,
        "voice_name": record.get("voice_name", ""),
        "deleted_dir": str(voice_dir),
        "remaining_voices": len(remaining_records),
    }
