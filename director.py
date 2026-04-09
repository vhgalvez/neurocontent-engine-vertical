# director.py

import csv
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List

import requests

from config import (
    INDEX_FILE,
    JOB_ID_WIDTH,
    OLLAMA_MAX_RETRIES,
    OLLAMA_URL,
    OPTIONS,
    REQUEST_TIMEOUT_SECONDS,
    get_text_model,
    get_runtime_paths,
)
from job_paths import JobPaths, build_job_paths, ensure_job_structure, first_existing_path
from prompts import (
    REWRITE_SYSTEM_SCRIPT,
    REWRITE_USER_SCRIPT,
    SYSTEM_SCRIPT,
    USER_SCRIPT,
)
from voice_registry import load_job_document, now_iso, save_job_document

SCRIPT_REQUIRED_KEYS = {
    "hook",
    "problema",
    "explicacion",
    "solucion",
    "cierre",
    "cta",
    "guion_narrado",
}

RENDER_TARGET_ORDER = ["vertical", "horizontal"]
RENDER_TARGET_ASPECT_RATIO = {
    "vertical": "9:16",
    "horizontal": "16:9",
}
RENDER_TARGET_SAFE_AREA = {
    "vertical": "center-weighted mobile frame",
    "horizontal": "wider composition for desktop and long-form framing",
}
RENDER_TARGET_PLATFORM_BEHAVIOR = {
    "vertical": "short-form vertical video, fast clarity, early payoff",
    "horizontal": "landscape framing, stronger lateral composition",
}
DEFAULT_RENDER_TARGETS = ["vertical"]
DEFAULT_RENDER_TARGET = "vertical"
DEFAULT_CONTENT_ORIENTATION = "portrait"
DEFAULT_TARGET_ASPECT_RATIOS = ["9:16"]

STATUS_DEFAULTS = {
    "brief_created": False,
    "script_generated": False,
    "audio_generated": False,
    "subtitles_generated": False,
    "visual_manifest_generated": False,
    "scene_prompt_pack_generated": False,
    "scene_prompt_pack_file": "",
    "scene_prompt_pack_markdown_file": "",
    "export_ready": False,
    "last_step": "created",
    "updated_at": "",
    "voice_id": "",
    "voice_scope": "",
    "voice_source": "",
    "voice_name": "",
    "voice_selection_mode": "",
    "voice_model_name": "",
    "voice_reference_file": "",
    "voice_mode": "",
    "tts_strategy_requested": "",
    "tts_strategy_used": "",
    "tts_fallback_used": False,
    "tts_fallback_reason": "",
    "voice_instruct_source": "",
    "seed_source": "",
    "preset_source": "",
    "runtime_source": "",
    "audio_file": "",
    "audio_generated_at": "",
    "render_targets": ["vertical"],
    "default_render_target": "vertical",
    "render_vertical_requested": True,
    "render_horizontal_requested": False,
    "render_vertical_ready": False,
    "render_horizontal_ready": False,
}

INDEX_COLUMNS = [
    "job_id",
    "source_id",
    "estado_csv",
    "idea_central",
    "platform",
    "language",
    "render_targets",
    "default_render_target",
    "content_orientation",
    "brief_created",
    "script_generated",
    "audio_generated",
    "subtitles_generated",
    "visual_manifest_generated",
    "export_ready",
    "last_step",
    "updated_at",
]

TRANSITION_MARKERS = {
    "porque",
    "pero",
    "entonces",
    "por eso",
    "asi que",
    "ahora",
    "si no",
    "mientras",
    "aunque",
    "primero",
    "despues",
    "al final",
    "y ahi",
    "por eso mismo",
    "de hecho",
}


class OllamaError(Exception):
    """Error controlado al interactuar con Ollama."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pad_job_id(value: Any) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("El brief no contiene un id utilizable.")
    return raw.zfill(JOB_ID_WIDTH)


def get_job_paths(job_id: str) -> JobPaths:
    return ensure_job_structure(build_job_paths(job_id, get_runtime_paths()))


def safe_write_json(path: Path, data: Dict[str, Any] | List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def safe_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        file.write(content)


def safe_read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_primary_or_legacy(primary: Path, legacy_candidates: list[Path], default: Any | None = None) -> Any:
    resolved = first_existing_path(primary, legacy_candidates)
    return safe_read_json(resolved, default=default)


def _parse_pipe_values(value: Any) -> List[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split("|") if item.strip()]


def _ordered_unique(items: List[str], allowed: List[str] | None = None) -> List[str]:
    allowed_set = set(allowed or items)
    unique: List[str] = []
    for item in items:
        if item in allowed_set and item not in unique:
            unique.append(item)
    return unique


def _parse_render_targets(brief: Dict[str, Any]) -> List[str]:
    parsed = _ordered_unique(_parse_pipe_values(brief.get("render_targets")), RENDER_TARGET_ORDER)
    return parsed or DEFAULT_RENDER_TARGETS.copy()


def _resolve_default_render_target(brief: Dict[str, Any], render_targets: List[str]) -> str:
    candidate = str(brief.get("default_render_target", "") or "").strip().lower()
    if candidate in render_targets:
        return candidate
    if render_targets:
        return render_targets[0]
    return DEFAULT_RENDER_TARGET


def _resolve_content_orientation(brief: Dict[str, Any], render_targets: List[str]) -> str:
    candidate = str(brief.get("content_orientation", "") or "").strip().lower()
    if candidate in {"portrait", "landscape", "multi"}:
        return candidate
    if len(render_targets) > 1:
        return "multi"
    if render_targets == ["horizontal"]:
        return "landscape"
    return DEFAULT_CONTENT_ORIENTATION


def _resolve_target_aspect_ratios(brief: Dict[str, Any], render_targets: List[str]) -> List[str]:
    supported = list(RENDER_TARGET_ASPECT_RATIO.values())
    parsed = _ordered_unique(_parse_pipe_values(brief.get("target_aspect_ratio")), supported)
    expected = [RENDER_TARGET_ASPECT_RATIO[target] for target in render_targets] or DEFAULT_TARGET_ASPECT_RATIOS
    if len(render_targets) > 1:
        return expected
    if parsed and parsed[0] == expected[0]:
        return [expected[0]]
    return [expected[0]]


def _build_render_profiles(render_targets: List[str]) -> Dict[str, Dict[str, str]]:
    profiles: Dict[str, Dict[str, str]] = {}
    for target in render_targets:
        profiles[target] = {
            "aspect_ratio": RENDER_TARGET_ASPECT_RATIO[target],
            "safe_area": RENDER_TARGET_SAFE_AREA[target],
            "platform_behavior": RENDER_TARGET_PLATFORM_BEHAVIOR[target],
        }
    return profiles


def resolve_render_config(brief: Dict[str, Any]) -> Dict[str, Any]:
    render_targets = _parse_render_targets(brief)
    default_target = _resolve_default_render_target(brief, render_targets)
    content_orientation = _resolve_content_orientation(brief, render_targets)
    aspect_ratios = _resolve_target_aspect_ratios(brief, render_targets)
    render_profiles = _build_render_profiles(render_targets)
    return {
        "targets": render_targets,
        "default_target": default_target,
        "content_orientation": content_orientation,
        "aspect_ratios": aspect_ratios,
        "render_profiles": render_profiles,
        "targets_csv": "|".join(render_targets),
        "aspect_ratios_csv": "|".join(aspect_ratios),
    }


def _render_status_fields(render_config: Dict[str, Any]) -> Dict[str, Any]:
    targets = set(render_config["targets"])
    return {
        "render_targets": render_config["targets"],
        "default_render_target": render_config["default_target"],
        "render_vertical_requested": "vertical" in targets,
        "render_horizontal_requested": "horizontal" in targets,
        "render_vertical_ready": False,
        "render_horizontal_ready": False,
    }


def _render_config_from_job_document(job_document: Dict[str, Any]) -> Dict[str, Any]:
    render = job_document.get("render") or {}
    brief_like = {
        "render_targets": "|".join(render.get("targets", []) or []),
        "default_render_target": render.get("default_target", ""),
        "content_orientation": render.get("content_orientation", ""),
        "target_aspect_ratio": "|".join(render.get("aspect_ratios", []) or []),
    }
    return resolve_render_config(brief_like)


def load_status(status_path: Path) -> Dict[str, Any]:
    current = safe_read_json(status_path, default={}) or {}
    status = {**STATUS_DEFAULTS, **current}
    if isinstance(status.get("render_targets"), str):
        status["render_targets"] = _parse_pipe_values(status["render_targets"]) or DEFAULT_RENDER_TARGETS.copy()
    elif not isinstance(status.get("render_targets"), list):
        status["render_targets"] = DEFAULT_RENDER_TARGETS.copy()
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    return status


def update_status(
    status_path: Path,
    *,
    last_step: str | None = None,
    **changes: Any,
) -> Dict[str, Any]:
    status = load_status(status_path)
    status.update(changes)
    if last_step:
        status["last_step"] = last_step
    status["updated_at"] = utc_now_iso()
    status["export_ready"] = bool(
        status["brief_created"]
        and status["script_generated"]
        and status["audio_generated"]
        and status["subtitles_generated"]
        and status["visual_manifest_generated"]
    )
    safe_write_json(status_path, status)
    return status


def sync_status_with_files(paths: JobPaths) -> Dict[str, Any]:
    job_document = load_job_document(paths)
    render_config = _render_config_from_job_document(job_document)
    voice = job_document.get("voice") or {}
    audio_synthesis = job_document.get("audio_synthesis") or {}
    artifacts = job_document.get("artifacts") or {}
    audio_artifact = artifacts.get("audio") or {}
    return update_status(
        paths.status,
        brief_created=first_existing_path(paths.brief, paths.legacy_brief_candidates).exists(),
        script_generated=first_existing_path(paths.script, paths.legacy_script_candidates).exists(),
        audio_generated=first_existing_path(paths.audio, paths.legacy_audio_candidates).exists(),
        subtitles_generated=first_existing_path(paths.subtitles, paths.legacy_subtitles_candidates).exists(),
        visual_manifest_generated=first_existing_path(paths.manifest, paths.legacy_manifest_candidates).exists(),
        scene_prompt_pack_generated=paths.scene_prompt_pack.exists() and paths.scene_prompt_pack_markdown.exists(),
        scene_prompt_pack_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack) if paths.scene_prompt_pack.exists() else "",
        scene_prompt_pack_markdown_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack_markdown) if paths.scene_prompt_pack_markdown.exists() else "",
        voice_id=voice.get("voice_id", ""),
        voice_scope=voice.get("scope", ""),
        voice_source=voice.get("voice_source", voice.get("selection_mode", "")),
        voice_name=voice.get("voice_name", ""),
        voice_selection_mode=voice.get("selection_mode", ""),
        voice_model_name=voice.get("model_name", ""),
        voice_reference_file=voice.get("reference_file", "") or "",
        voice_mode=voice.get("voice_mode", ""),
        tts_strategy_requested=audio_synthesis.get("tts_strategy_requested", ""),
        tts_strategy_used=audio_synthesis.get("tts_strategy_used", ""),
        tts_fallback_used=bool(audio_synthesis.get("tts_fallback_used", False)),
        tts_fallback_reason=audio_synthesis.get("tts_fallback_reason", ""),
        voice_instruct_source=audio_synthesis.get("voice_instruct_source", ""),
        seed_source=audio_synthesis.get("seed_source", ""),
        preset_source=audio_synthesis.get("preset_source", ""),
        runtime_source=audio_synthesis.get("runtime_source", ""),
        audio_file=audio_artifact.get("file", ""),
        audio_generated_at=audio_artifact.get("generated_at", ""),
        **_render_status_fields(render_config),
    )


def ensure_job_metadata(paths: JobPaths, brief: Dict[str, Any]) -> Dict[str, Any]:
    runtime = get_runtime_paths()
    document = load_job_document(paths)
    render_config = resolve_render_config(brief)
    story_id = str(brief.get("story_id") or brief.get("id") or "").strip()
    story_file = str(brief.get("story_file", "") or "").strip()
    document.update(
        {
            "job_id": paths.job_id,
            "job_schema_version": "2.0",
            "story_id": story_id,
            "story_file": story_file,
            "title": brief.get("idea_central", ""),
            "language": brief.get("idioma", ""),
            "platform": brief.get("plataforma", ""),
            "render": {
                "targets": render_config["targets"],
                "default_target": render_config["default_target"],
                "content_orientation": render_config["content_orientation"],
                "aspect_ratios": render_config["aspect_ratios"],
            },
            "dataset_root": runtime.dataset_root.as_posix(),
            "jobs_root": runtime.jobs_root.as_posix(),
            "paths": {
                "brief": runtime.to_dataset_relative(paths.brief),
                "script": runtime.to_dataset_relative(paths.script),
                "visual_manifest": runtime.to_dataset_relative(paths.manifest),
                "scene_prompt_pack": runtime.to_dataset_relative(paths.scene_prompt_pack),
                "scene_prompt_pack_markdown": runtime.to_dataset_relative(paths.scene_prompt_pack_markdown),
                "rendered_comfy_workflow": runtime.to_dataset_relative(paths.rendered_workflow),
                "audio": runtime.to_dataset_relative(paths.audio),
                "subtitles": runtime.to_dataset_relative(paths.subtitles),
                "logs_dir": runtime.to_dataset_relative(paths.logs_dir),
            },
            "updated_at": now_iso(),
        }
    )
    if not document.get("created_at"):
        document["created_at"] = now_iso()
    document.setdefault("artifacts", {})
    return save_job_document(paths, document)


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    raise OllamaError(f"No se encontro JSON valido en la respuesta:\n{cleaned}")


def _normalize_brief(brief: Dict[str, Any]) -> Dict[str, str]:
    expected_keys = {
        "id",
        "estado",
        "nicho",
        "subnicho",
        "idioma",
        "plataforma",
        "formato",
        "duracion_seg",
        "objetivo",
        "avatar",
        "audiencia",
        "dolor_principal",
        "deseo_principal",
        "miedo_principal",
        "angulo",
        "tipo_hook",
        "historia_base",
        "idea_central",
        "tesis",
        "enemigo",
        "error_comun",
        "transformacion_prometida",
        "tono",
        "emocion_principal",
        "emocion_secundaria",
        "nivel_intensidad",
        "cta_tipo",
        "cta_texto",
        "prohibido",
        "keywords",
        "referencias",
        "notas_direccion",
        "ritmo",
        "estilo_narracion",
        "tipo_cierre",
        "nivel_agresividad_copy",
        "objetivo_retencion",
        "render_targets",
        "default_render_target",
        "content_orientation",
        "target_aspect_ratio",
    }

    normalized: Dict[str, str] = {}
    for key in expected_keys:
        value = brief.get(key, "")
        normalized[key] = str(value).strip() if value is not None else ""

    render_config = resolve_render_config(brief)
    normalized["render_targets"] = render_config["targets_csv"]
    normalized["default_render_target"] = render_config["default_target"]
    normalized["content_orientation"] = render_config["content_orientation"]
    normalized["target_aspect_ratio"] = render_config["aspect_ratios_csv"]

    return normalized


def _clean_compare_text(text: str) -> str:
    normalized = " ".join(str(text).lower().split()).strip()
    normalized = re.sub(r"[^\wáéíóúüñ\s]", "", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _remove_exact_cta(text: str, cta: str) -> str:
    text_norm = " ".join(str(text).split()).strip()
    cta_norm = " ".join(str(cta).split()).strip()

    if not cta_norm:
        return text_norm

    if text_norm.endswith(cta_norm):
        return text_norm[: -len(cta_norm)].strip(" .,!?:;")

    return text_norm


def build_prompt(brief: Dict[str, Any]) -> str:
    normalized = _normalize_brief(brief)
    return USER_SCRIPT.format(**normalized)


def build_naive_narration(script_data: Dict[str, Any], include_cta: bool = False) -> str:
    pieces = [
        script_data.get("hook", ""),
        script_data.get("problema", ""),
        script_data.get("explicacion", ""),
        *script_data.get("solucion", []),
        script_data.get("cierre", ""),
    ]

    if include_cta:
        pieces.append(script_data.get("cta", ""))

    return " ".join(
        " ".join(str(piece).split()) for piece in pieces if str(piece).strip()
    ).strip()


def _count_exact_block_reuse(script_data: Dict[str, Any], narration: str) -> int:
    narration_clean = _clean_compare_text(narration)

    blocks = [
        script_data.get("hook", ""),
        script_data.get("problema", ""),
        script_data.get("explicacion", ""),
        *script_data.get("solucion", []),
        script_data.get("cierre", ""),
    ]

    reused = 0
    for block in blocks:
        block_clean = _clean_compare_text(block)
        if block_clean and block_clean in narration_clean:
            reused += 1
    return reused


def _should_try_rewrite(exc: OllamaError) -> bool:
    text = str(exc).lower()
    rewrite_triggers = [
        "concatenacion mecanica",
        "guion_narrado",
        "transiciones naturales",
        "demasiado corto",
        "bloques literales",
    ]
    return any(trigger in text for trigger in rewrite_triggers)


def _ollama_chat_json(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    payload = {
        "model": get_text_model(),
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": OPTIONS,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise OllamaError(f"Error Ollama ({response.status_code}):\n{response.text}")

    try:
        data = response.json()
    except ValueError:
        raise OllamaError(f"Ollama devolvio una respuesta no JSON:\n{response.text}")

    message = data.get("message")
    if not isinstance(message, dict):
        raise OllamaError(
            "Respuesta inesperada de Ollama: falta 'message'.\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )

    content = message.get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise OllamaError(
            "La respuesta de Ollama no contiene texto utilizable.\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )

    return _extract_json_from_text(content)


def rewrite_guion_narrado(brief: Dict[str, Any], script_data: Dict[str, Any]) -> str:
    normalized_brief = _normalize_brief(brief)

    rewrite_prompt = REWRITE_USER_SCRIPT.format(
        idea_central=normalized_brief["idea_central"],
        plataforma=normalized_brief["plataforma"],
        duracion_seg=normalized_brief["duracion_seg"],
        tono=normalized_brief["tono"],
        ritmo=normalized_brief["ritmo"],
        emocion_principal=normalized_brief["emocion_principal"],
        emocion_secundaria=normalized_brief["emocion_secundaria"],
        cta_texto=normalized_brief["cta_texto"],
        script_json=json.dumps(script_data, ensure_ascii=False, indent=2),
    )

    rewrite_data = _ollama_chat_json(
        [
            {"role": "system", "content": REWRITE_SYSTEM_SCRIPT.strip()},
            {"role": "user", "content": rewrite_prompt.strip()},
        ]
    )

    guion_narrado = rewrite_data.get("guion_narrado", "")
    if not isinstance(guion_narrado, str) or not guion_narrado.strip():
        raise OllamaError("La reescritura de guion_narrado devolvio texto vacio.")

    return " ".join(guion_narrado.split()).strip()


def _sentence_chunks(text: str) -> List[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def validate_script_data(script_data: Dict[str, Any]) -> None:
    missing = SCRIPT_REQUIRED_KEYS - set(script_data.keys())
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise OllamaError(
            "El JSON devuelto no tiene todas las claves requeridas. "
            f"Faltan: {missing_text}\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    if not isinstance(script_data["solucion"], list) or len(script_data["solucion"]) != 3:
        raise OllamaError(
            "La clave 'solucion' debe ser una lista de exactamente 3 pasos.\n"
            f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
        )

    for key in ("hook", "problema", "explicacion", "cierre", "cta", "guion_narrado"):
        if not isinstance(script_data[key], str) or not script_data[key].strip():
            raise OllamaError(
                f"La clave '{key}' debe ser texto no vacio.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )

    for index, step in enumerate(script_data["solucion"], start=1):
        if not isinstance(step, str) or not step.strip():
            raise OllamaError(
                f"El paso {index} de 'solucion' esta vacio o no es texto.\n"
                f"Respuesta: {json.dumps(script_data, ensure_ascii=False, indent=2)}"
            )

    narration = " ".join(script_data["guion_narrado"].split()).strip()
    narration_without_cta = _remove_exact_cta(narration, script_data["cta"])
    naive_narration = build_naive_narration(script_data, include_cta=False)
    sentence_chunks = _sentence_chunks(narration)
    lower_narration = narration.lower()

    similarity = SequenceMatcher(
        None,
        _clean_compare_text(narration_without_cta),
        _clean_compare_text(naive_narration),
    ).ratio()
    exact_reuse = _count_exact_block_reuse(script_data, narration_without_cta)

    if len(sentence_chunks) < 4:
        raise OllamaError("guion_narrado debe tener al menos 4 frases completas.")
    if len(narration.split()) < 40:
        raise OllamaError("guion_narrado es demasiado corto para TTS natural.")
    if similarity > 0.92 and exact_reuse >= 4:
        raise OllamaError(
            "guion_narrado se parece demasiado a una concatenacion mecanica de bloques."
        )
    if exact_reuse >= 5:
        raise OllamaError(
            "guion_narrado reutiliza demasiados bloques literales del esquema original."
        )
    if not any(marker in lower_narration for marker in TRANSITION_MARKERS):
        raise OllamaError(
            "guion_narrado no muestra transiciones naturales suficientes entre ideas."
        )


def _normalize_script_data(script_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hook": script_data["hook"].strip(),
        "problema": script_data["problema"].strip(),
        "explicacion": script_data["explicacion"].strip(),
        "solucion": [step.strip() for step in script_data["solucion"]],
        "cierre": script_data["cierre"].strip(),
        "cta": script_data["cta"].strip(),
        "guion_narrado": " ".join(script_data["guion_narrado"].split()).strip(),
    }


def generate_script(brief: Dict[str, Any]) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_SCRIPT.strip()},
        {"role": "user", "content": build_prompt(brief).strip()},
    ]

    last_error: Exception | None = None

    for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
        try:
            script_data = _ollama_chat_json(messages)

            try:
                validate_script_data(script_data)
            except OllamaError as validation_error:
                if _should_try_rewrite(validation_error):
                    try:
                        script_data["guion_narrado"] = rewrite_guion_narrado(brief, script_data)
                        validate_script_data(script_data)
                    except OllamaError as rewrite_error:
                        last_error = OllamaError(
                            f"Intento {attempt} invalido tras reescritura: {rewrite_error}"
                        )
                        continue
                else:
                    last_error = OllamaError(
                        f"Intento {attempt} invalido: {validation_error}"
                    )
                    continue

            return _normalize_script_data(script_data)
        except requests.RequestException as exc:
            last_error = OllamaError(f"No se pudo conectar con Ollama: {exc}")
            continue
        except OllamaError as exc:
            last_error = exc
            continue

    if last_error:
        raise last_error
    raise OllamaError("No fue posible generar un guion valido con Ollama.")


def _duration_seconds(brief: Dict[str, Any]) -> int:
    duration_raw = str(brief.get("duracion_seg", "0")).strip() or "0"
    try:
        return max(0, int(float(duration_raw)))
    except ValueError:
        return 0


def _keywords_list(brief: Dict[str, Any]) -> List[str]:
    return [keyword.strip() for keyword in str(brief.get("keywords", "")).split(",") if keyword.strip()]


def _character_design(brief: Dict[str, Any]) -> Dict[str, Any]:
    render_config = resolve_render_config(brief)
    if render_config["content_orientation"] == "multi":
        persona_function = (
            "credible narrator or protagonist for short-form content that remains legible "
            "across vertical and horizontal downstream renders"
        )
    else:
        persona_function = (
            "credible narrator or protagonist for short-form content who embodies "
            "the problem-to-solution arc of the brief"
        )

    return {
        "identity_anchor": brief.get("avatar", ""),
        "audience_mirror": brief.get("audiencia", ""),
        "persona_function": persona_function,
        "tone_alignment": brief.get("tono", ""),
        "styling_notes": brief.get("notas_direccion", ""),
        "consistency_rules": [
            "keep the same subject identity across all scenes unless the scene explicitly uses metaphor",
            "preserve wardrobe, age range, and general look continuity across the full piece",
            "match facial expression and body language to the emotional arc of each beat",
        ],
    }


def _normalize_text_fragment(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _csv_style_terms(value: Any) -> List[str]:
    raw = str(value or "").replace("|", ",")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _join_prompt_parts(parts: List[str]) -> str:
    ordered: List[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = _normalize_text_fragment(part).strip(" ,")
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ", ".join(ordered)


def _infer_asset_preference(scene_role: str, scene: Dict[str, Any], visual_style: Dict[str, Any]) -> str:
    role = str(scene_role or "").strip().lower()
    transition = str(scene.get("transition", "")).lower()
    camera = str(scene.get("camera", "")).lower()
    rhythm = str(visual_style.get("rhythm", "")).lower()

    if role in {"hook", "cta", "problema"}:
        return "video"
    if role.startswith("solucion") and ("motion" in camera or "punch" in camera or "lateral" in camera):
        return "video"
    if "smash_cut" in transition or "cold_open" in transition:
        return "video"
    if rhythm in {"rapido", "rápido"} and role.startswith("solucion"):
        return "video"
    return "image"


def _workflow_profile_for_scene(scene_role: str) -> str:
    role = str(scene_role or "").strip().lower()
    if role == "hook":
        return "vertical_hook_qwen"
    if role == "problema":
        return "vertical_problem_qwen"
    if role in {"explicacion", "cierre"} or role.startswith("solucion"):
        return "vertical_explainer_qwen"
    if role == "cta":
        return "vertical_cta_qwen"
    return "vertical_scene_qwen"


def _build_prompt_negative(brief: Dict[str, Any], visual_style: Dict[str, Any]) -> str:
    forbidden_terms = _csv_style_terms(brief.get("prohibido", "")) + _csv_style_terms(visual_style.get("forbidden", ""))
    base_terms = [
        "blurry",
        "low quality",
        "pixelated",
        "bad anatomy",
        "extra fingers",
        "deformed hands",
        "distorted face",
        "duplicate subject",
        "cartoon",
        "3d render",
        "watermark",
        "logo",
        "text artifacts",
        "caption burn-in",
        "oversaturated",
        "cheap motivational aesthetic",
    ]
    return _join_prompt_parts(base_terms + forbidden_terms)


def _build_continuity_prompt(
    brief_context: Dict[str, Any],
    visual_style: Dict[str, Any],
    character_design: Dict[str, Any],
) -> str:
    identity = _normalize_text_fragment(character_design.get("identity_anchor"))
    audience = _normalize_text_fragment(character_design.get("audience_mirror"))
    style_notes = _normalize_text_fragment(visual_style.get("visual_notes"))
    references = _normalize_text_fragment(visual_style.get("references"))
    tone = _normalize_text_fragment(visual_style.get("tone"))
    pieces = [
        f"same core subject: {identity}" if identity else "",
        f"same audience-coded persona: {audience}" if audience else "",
        "same facial identity across all scenes",
        "same age range and wardrobe continuity across the full piece",
        "same lighting logic and vertical framing language",
        f"maintain tone: {tone}" if tone else "",
        f"keep visual direction consistent with: {style_notes}" if style_notes else "",
        f"respect style references: {references}" if references else "",
        f"anchor the transformation around: {_normalize_text_fragment(brief_context.get('promised_transformation'))}"
        if _normalize_text_fragment(brief_context.get("promised_transformation"))
        else "",
    ]
    return _join_prompt_parts(pieces)


def _build_action_prompt(scene: Dict[str, Any], asset_preference: str, visual_style: Dict[str, Any]) -> str:
    if asset_preference != "video":
        return ""

    role = str(scene.get("scene_role", "")).lower()
    rhythm = _normalize_text_fragment(visual_style.get("rhythm"))
    role_to_action = {
        "hook": "subtle head motion, tense breathing, micro-expression shift, slight camera punch-in energy",
        "problema": "restless body language, stress gestures, pacing or reactive movement, handheld tension",
        "explicacion": "measured hand gesture, overlay-friendly beat, controlled presenter motion",
        "cierre": "steady eye contact, minimal deliberate movement, stronger final hold",
        "cta": "direct-to-camera gesture, confident invitation, clean end-frame hold",
    }
    if role.startswith("solucion"):
        return _join_prompt_parts([
            "practical hand movement that demonstrates the step",
            "small forward motion that signals progress",
            f"editing rhythm: {rhythm}" if rhythm else "",
        ])
    return _join_prompt_parts([
        role_to_action.get(role, "controlled presenter motion aligned with the narration beat"),
        f"editing rhythm: {rhythm}" if rhythm else "",
    ])


def _build_prompt_positive(
    scene: Dict[str, Any],
    brief: Dict[str, Any],
    brief_context: Dict[str, Any],
    visual_style: Dict[str, Any],
    character_design: Dict[str, Any],
    asset_preference: str,
) -> str:
    keywords = _csv_style_terms(visual_style.get("keywords", ""))
    positive_parts = [
        _normalize_text_fragment(character_design.get("identity_anchor")),
        _normalize_text_fragment(scene.get("visual_intent")),
        _normalize_text_fragment(scene.get("camera")),
        _normalize_text_fragment(scene.get("mood")),
        _normalize_text_fragment(scene.get("text")),
        _normalize_text_fragment(brief.get("idea_central")),
        _normalize_text_fragment(brief_context.get("audience")),
        _normalize_text_fragment(brief_context.get("thesis")),
        _normalize_text_fragment(visual_style.get("references")),
        _normalize_text_fragment(visual_style.get("visual_notes")),
        "vertical 9:16 composition",
        "cinematic realism",
        "social-first framing",
        "high detail skin and wardrobe realism",
        "clear subject separation",
        "micro-contrast lighting",
        "short-form ad-like immediacy" if asset_preference == "video" else "single keyframe clarity",
    ]
    return _join_prompt_parts(positive_parts + keywords)


def _build_copy_paste_block(
    prompt_positive: str,
    prompt_negative: str,
    action_prompt: str,
    continuity_prompt: str,
    workflow_profile: str,
    asset_preference: str,
) -> Dict[str, Any]:
    return {
        "positive_prompt": prompt_positive,
        "negative_prompt": prompt_negative,
        "action_prompt": action_prompt,
        "continuity_prompt": continuity_prompt,
        "workflow_profile": workflow_profile,
        "asset_preference": asset_preference,
        "seed": 424242,
    }


def build_scene_prompt_pack(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    visual_manifest: Dict[str, Any],
    job_id: str,
) -> Dict[str, Any]:
    brief_context = visual_manifest.get("brief_context") or {}
    script_context = visual_manifest.get("script_context") or {}
    visual_style = visual_manifest.get("visual_style") or {}
    character_design = visual_manifest.get("character_design") or {}
    scene_plan = visual_manifest.get("scene_plan") or []
    continuity_prompt = _build_continuity_prompt(brief_context, visual_style, character_design)
    prompt_negative = _build_prompt_negative(brief, visual_style)

    scenes: List[Dict[str, Any]] = []
    for scene in scene_plan:
        asset_preference = _infer_asset_preference(scene.get("scene_role", ""), scene, visual_style)
        workflow_profile = _workflow_profile_for_scene(scene.get("scene_role", ""))
        prompt_positive = _build_prompt_positive(
            scene=scene,
            brief=brief,
            brief_context=brief_context,
            visual_style=visual_style,
            character_design=character_design,
            asset_preference=asset_preference,
        )
        action_prompt = _build_action_prompt(scene, asset_preference, visual_style)
        scenes.append(
            {
                "scene_id": scene.get("scene_id", ""),
                "scene_role": scene.get("scene_role", ""),
                "start_sec": scene.get("start_sec"),
                "end_sec": scene.get("end_sec"),
                "text": scene.get("text", ""),
                "prompt_positive": prompt_positive,
                "prompt_negative": prompt_negative,
                "action_prompt": action_prompt,
                "continuity_prompt": continuity_prompt,
                "camera": scene.get("camera", ""),
                "mood": scene.get("mood", ""),
                "transition": scene.get("transition", ""),
                "visual_intent": scene.get("visual_intent", ""),
                "asset_preference": asset_preference,
                "workflow_profile": workflow_profile,
                "copy_paste_block": _build_copy_paste_block(
                    prompt_positive=prompt_positive,
                    prompt_negative=prompt_negative,
                    action_prompt=action_prompt,
                    continuity_prompt=continuity_prompt,
                    workflow_profile=workflow_profile,
                    asset_preference=asset_preference,
                ),
            }
        )

    return {
        "scene_prompt_pack_version": "1.0",
        "job_id": job_id,
        "title": visual_manifest.get("title", brief.get("idea_central", "")),
        "workflow_target": "comfyui_manual_copy_paste",
        "source_of_truth": {
            "brief_file": visual_manifest.get("job_files", {}).get("brief", ""),
            "script_file": visual_manifest.get("job_files", {}).get("script", ""),
            "visual_manifest_file": visual_manifest.get("job_files", {}).get("visual_manifest", ""),
        },
        "editorial_context": {
            "brief_context": brief_context,
            "script_context": {
                "hook": script_context.get("hook", script.get("hook", "")),
                "problem": script_context.get("problem", script.get("problema", "")),
                "explanation": script_context.get("explanation", script.get("explicacion", "")),
                "solution": script_context.get("solution", script.get("solucion", [])),
                "close": script_context.get("close", script.get("cierre", "")),
                "cta": script_context.get("cta", script.get("cta", "")),
            },
            "visual_style": visual_style,
            "character_design": character_design,
        },
        "scenes": scenes,
    }


def render_scene_prompt_pack_markdown(pack: Dict[str, Any]) -> str:
    lines = [
        f"# Scene Prompt Pack {pack.get('job_id', '')}",
        "",
        f"TITLE: {pack.get('title', '')}",
        f"WORKFLOW_TARGET: {pack.get('workflow_target', '')}",
        "",
    ]

    for scene in pack.get("scenes", []):
        lines.extend(
            [
                f"SCENE_ID: {scene.get('scene_id', '')}",
                f"SCENE_ROLE: {scene.get('scene_role', '')}",
                f"START_SEC: {scene.get('start_sec', '')}",
                f"END_SEC: {scene.get('end_sec', '')}",
                f"CAMERA: {scene.get('camera', '')}",
                f"MOOD: {scene.get('mood', '')}",
                f"TRANSITION: {scene.get('transition', '')}",
                f"VISUAL_INTENT: {scene.get('visual_intent', '')}",
                "",
                "TEXT:",
                str(scene.get("text", "")),
                "",
                "POSITIVE_PROMPT:",
                str(scene.get("prompt_positive", "")),
                "",
                "NEGATIVE_PROMPT:",
                str(scene.get("prompt_negative", "")),
                "",
                "ACTION_PROMPT:",
                str(scene.get("action_prompt", "")),
                "",
                "CONTINUITY_PROMPT:",
                str(scene.get("continuity_prompt", "")),
                "",
                f"ASSET_PREFERENCE: {scene.get('asset_preference', '')}",
                f"WORKFLOW_PROFILE: {scene.get('workflow_profile', '')}",
                "",
                "COPY_PASTE_BLOCK:",
                json.dumps(scene.get("copy_paste_block", {}), ensure_ascii=False, indent=2),
                "",
                "---",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def generate_scene_prompt_pack(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    visual_manifest: Dict[str, Any],
    paths: JobPaths,
) -> Dict[str, Any]:
    pack = build_scene_prompt_pack(
        brief=brief,
        script=script,
        visual_manifest=visual_manifest,
        job_id=paths.job_id,
    )
    safe_write_json(paths.scene_prompt_pack, pack)
    safe_write_text(paths.scene_prompt_pack_markdown, render_scene_prompt_pack_markdown(pack))
    update_status(
        paths.status,
        scene_prompt_pack_generated=True,
        scene_prompt_pack_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack),
        scene_prompt_pack_markdown_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack_markdown),
        last_step="scene_prompt_pack_generated",
    )
    return pack


def _scene_transition(index: int, total: int, role: str) -> str:
    if index == 1:
        return "cold_open"
    if role.startswith("solucion"):
        return "motivated_match_cut"
    if index == total:
        return "clean_end_hold"
    if role == "problema":
        return "smash_cut"
    if role == "explicacion":
        return "graphic_overlay_transition"
    return "fast_continuity_cut"


def _scene_specs(script: Dict[str, Any], brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    solucion = script.get("solucion", ["", "", ""])
    while len(solucion) < 3:
        solucion.append("")

    return [
        {
            "role": "hook",
            "text": script.get("hook", ""),
            "visual_intent": (
                "Open with an arresting visual contradiction that stops the scroll and "
                "frames the core thesis immediately."
            ),
            "camera": "extreme close-up or punch-in opening frame, direct subject emphasis",
            "mood": f"{brief.get('emocion_principal', 'tension')} and immediate urgency",
            "edit_intent": "start cold, first-frame clarity, aggressive pattern interrupt",
        },
        {
            "role": "problema",
            "text": script.get("problema", ""),
            "visual_intent": "Show the pain point as a lived consequence, not as an abstract statement.",
            "camera": "close-up with subtle handheld energy or invasive crop",
            "mood": f"{brief.get('emocion_principal', 'tension')} with discomfort",
            "edit_intent": "tight pacing, reactive cutaways, lived friction",
        },
        {
            "role": "explicacion",
            "text": script.get("explicacion", ""),
            "visual_intent": "Make the hidden mechanism legible through symbolic or causal imagery.",
            "camera": "medium close-up with graphic overlays or conceptual inserts",
            "mood": f"{brief.get('tono', 'directo')} with clarity",
            "edit_intent": "explain without slowing down, visual logic over exposition",
        },
        {
            "role": "solucion_1",
            "text": solucion[0],
            "visual_intent": "Present the first corrective move as immediate and executable.",
            "camera": "medium shot with decisive gesture or practical action",
            "mood": "clarity and momentum",
            "edit_intent": "clean instructional beat, no fluff",
        },
        {
            "role": "solucion_2",
            "text": solucion[1],
            "visual_intent": "Escalate from awareness to a repeatable habit or system.",
            "camera": "alternating close-up and insert detail for rhythm",
            "mood": "control and progression",
            "edit_intent": "show process, reinforce memorability",
        },
        {
            "role": "solucion_3",
            "text": solucion[2],
            "visual_intent": "Land the final action as the bridge to transformation.",
            "camera": "punch-in or lateral motion with stronger forward drive",
            "mood": f"{brief.get('emocion_secundaria', 'resolve')} with confidence",
            "edit_intent": "build toward payoff, stronger motion and contrast",
        },
        {
            "role": "cierre",
            "text": script.get("cierre", ""),
            "visual_intent": "Deliver the emotional payoff or wake-up call with conviction.",
            "camera": "steady medium close-up, hold slightly longer for impact",
            "mood": f"{brief.get('emocion_secundaria', 'impact')} with finality",
            "edit_intent": "slightly slower beat to let the message land",
        },
        {
            "role": "cta",
            "text": script.get("cta", ""),
            "visual_intent": "Close with a direct action cue that feels native to the platform.",
            "camera": "direct-to-camera end frame or simple branded end-card",
            "mood": "decisive and inviting",
            "edit_intent": "clean end beat, readable CTA, room for captions",
        },
    ]


def _distribute_sentences_across_scenes(
    sentence_chunks: List[str],
    specs: List[Dict[str, Any]],
) -> List[List[str]]:
    total = len(specs)
    groups: List[List[str]] = [[] for _ in range(total)]
    sentence_index = 0

    for spec_index, spec in enumerate(specs):
        role = spec["role"]
        remaining_scenes = total - spec_index
        remaining_sentences = len(sentence_chunks) - sentence_index
        if remaining_sentences <= 0:
            break

        take_count = 1
        if role in {"problema", "explicacion", "cierre"}:
            take_count = 1 if remaining_sentences <= remaining_scenes else 2

        max_allowed = max(1, remaining_sentences - (remaining_scenes - 1))
        take_count = min(take_count, max_allowed)

        for _ in range(take_count):
            groups[spec_index].append(sentence_chunks[sentence_index])
            sentence_index += 1

    while sentence_index < len(sentence_chunks):
        groups[-1].append(sentence_chunks[sentence_index])
        sentence_index += 1

    return groups


def _scene_time_ranges(duration_sec: int, total_scenes: int) -> List[Dict[str, float]]:
    if total_scenes <= 0:
        return []
    if duration_sec <= 0:
        return [
            {"start_sec": round(float(index), 2), "end_sec": round(float(index + 1), 2)}
            for index in range(total_scenes)
        ]

    weights = [0.9 if index == 0 else 0.8 if index == total_scenes - 1 else 1.0 for index in range(total_scenes)]
    total_weight = sum(weights)
    raw_durations = [duration_sec * (weight / total_weight) for weight in weights]

    current = 0.0
    ranges = []
    for index, raw_duration in enumerate(raw_durations):
        start = current
        end = duration_sec if index == total_scenes - 1 else current + raw_duration
        ranges.append({"start_sec": round(start, 2), "end_sec": round(end, 2)})
        current = end
    return ranges


def _build_scene_plan(script: Dict[str, Any], brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    narration = script.get("guion_narrado", "")
    sentence_chunks = _sentence_chunks(narration) or ([narration] if narration else [])
    specs = [spec for spec in _scene_specs(script, brief) if str(spec["text"]).strip()]
    if not specs:
        return []

    duration_sec = _duration_seconds(brief)
    keyword_list = _keywords_list(brief)
    groups = _distribute_sentences_across_scenes(sentence_chunks, specs)
    time_ranges = _scene_time_ranges(duration_sec, len(specs))
    character_design = _character_design(brief)
    render_config = resolve_render_config(brief)
    default_target = render_config["default_target"]
    default_profile = render_config["render_profiles"][default_target]

    scene_plan: List[Dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        narration_focus = " ".join(groups[index - 1]).strip() or spec["text"]
        scene_range = time_ranges[index - 1] if index - 1 < len(time_ranges) else {"start_sec": None, "end_sec": None}
        transition = _scene_transition(index, len(specs), spec["role"])
        base_prompt = {
            "subject": character_design["identity_anchor"],
            "context": brief.get("idea_central", ""),
            "action": spec["text"],
            "environment": brief.get("historia_base", "") or brief.get("audiencia", ""),
            "style": brief.get("notas_direccion", "") or brief.get("referencias", ""),
            "keywords": keyword_list,
            "platform_bias": brief.get("plataforma", ""),
            "render_targets": render_config["targets"],
            "default_render_target": default_target,
            "content_orientation": render_config["content_orientation"],
            "aspect_ratio": default_profile["aspect_ratio"],
            "motion_cue": brief.get("ritmo", ""),
            "composition_goal": spec["camera"],
            "negative_prompt": brief.get("prohibido", ""),
        }
        scene_plan.append(
            {
                "scene_id": f"scene_{index:02d}",
                "scene_role": spec["role"],
                "start_sec": scene_range["start_sec"],
                "end_sec": scene_range["end_sec"],
                "text": narration_focus,
                "visual_intent": spec["visual_intent"],
                "camera": spec["camera"],
                "mood": spec["mood"],
                "transition": transition,
                "comfy_prompt_base": {
                    **base_prompt,
                    "workflow_hint": "single keyframe or key shot for downstream ComfyUI generation/editing",
                    "continuity_anchor": character_design["identity_anchor"],
                    "edit_intent": spec["edit_intent"],
                },
                "wan_prompt_base": {
                    **base_prompt,
                    "workflow_hint": "short motion beat for downstream Wan 2.2 video generation/editing",
                    "continuity_anchor": character_design["identity_anchor"],
                    "transition_hint": transition,
                    "motion_emphasis": brief.get("ritmo", ""),
                },
            }
        )
    return scene_plan


def build_visual_manifest(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    job_id: str,
    audio_path: Path,
    subtitles_path: Path,
) -> Dict[str, Any]:
    runtime = get_runtime_paths()
    paths = get_job_paths(job_id)
    job_document = load_job_document(paths)
    render_config = _render_config_from_job_document(job_document)
    default_target = render_config["default_target"]
    default_profile = render_config["render_profiles"][default_target]

    return {
        "manifest_version": "2.0",
        "pipeline_role": "editorial_preproduction_only",
        "downstream_target": "visual_repo_for_comfyui_wan_multimodal_editing",
        "id": job_id,
        "title": brief.get("idea_central", ""),
        "platform": brief.get("plataforma", ""),
        "language": brief.get("idioma", ""),
        "duration_sec": _duration_seconds(brief),
        "render_targets": render_config["targets"],
        "default_render_target": default_target,
        "content_orientation": render_config["content_orientation"],
        "target_aspect_ratios": render_config["aspect_ratios"],
        "render_profiles": render_config["render_profiles"],
        "job": {
            "job_id": job_id,
            "job_schema_version": job_document.get("job_schema_version", "2.0"),
            "job_file": runtime.to_dataset_relative(paths.job_file),
            "status_file": runtime.to_dataset_relative(paths.status),
        },
        "job_files": {
            "brief": runtime.to_dataset_relative(paths.brief),
            "script": runtime.to_dataset_relative(paths.script),
            "visual_manifest": runtime.to_dataset_relative(paths.manifest),
            "scene_prompt_pack": runtime.to_dataset_relative(paths.scene_prompt_pack),
            "scene_prompt_pack_markdown": runtime.to_dataset_relative(paths.scene_prompt_pack_markdown),
            "rendered_comfy_workflow": runtime.to_dataset_relative(paths.rendered_workflow),
            "audio": runtime.to_dataset_relative(audio_path),
            "subtitles": runtime.to_dataset_relative(subtitles_path),
            "logs_dir": runtime.to_dataset_relative(paths.logs_dir),
        },
        "voice_assignment": job_document.get("voice", {}),
        "brief_context": {
            "niche": brief.get("nicho", ""),
            "subniche": brief.get("subnicho", ""),
            "objective": brief.get("objetivo", ""),
            "audience": brief.get("audiencia", ""),
            "avatar": brief.get("avatar", ""),
            "core_pain": brief.get("dolor_principal", ""),
            "core_desire": brief.get("deseo_principal", ""),
            "core_fear": brief.get("miedo_principal", ""),
            "angle": brief.get("angulo", ""),
            "thesis": brief.get("tesis", ""),
            "enemy": brief.get("enemigo", ""),
            "common_error": brief.get("error_comun", ""),
            "promised_transformation": brief.get("transformacion_prometida", ""),
            "retention_goal": brief.get("objetivo_retencion", ""),
        },
        "script_context": {
            "hook": script.get("hook", ""),
            "problem": script.get("problema", ""),
            "explanation": script.get("explicacion", ""),
            "solution": script.get("solucion", []),
            "close": script.get("cierre", ""),
            "cta": script.get("cta", ""),
            "guion_narrado": script.get("guion_narrado", ""),
            "narrative_arc": ["hook", "problem", "explanation", "solution", "close", "cta"],
        },
        "assets": {
            "audio": runtime.to_dataset_relative(audio_path),
            "subtitles": runtime.to_dataset_relative(subtitles_path),
        },
        "visual_style": {
            "tone": brief.get("tono", ""),
            "rhythm": brief.get("ritmo", ""),
            "narration_style": brief.get("estilo_narracion", ""),
            "emotional_primary": brief.get("emocion_principal", ""),
            "emotional_secondary": brief.get("emocion_secundaria", ""),
            "intensity": brief.get("nivel_intensidad", ""),
            "references": brief.get("referencias", ""),
            "visual_notes": brief.get("notas_direccion", ""),
            "keywords": brief.get("keywords", ""),
            "forbidden": brief.get("prohibido", ""),
        },
        "character_design": _character_design(brief),
        "edit_guidance": {
            "captions_source": "assets.subtitles",
            "voiceover_source": "assets.audio",
            "pacing": brief.get("ritmo", ""),
            "platform_native_behavior": default_profile["platform_behavior"],
            "primary_safe_area": default_profile["safe_area"],
            "notes": (
                "This repository stops at editorial preproduction. "
                "The downstream visual repository is responsible for visual generation, "
                "multimodal assembly and any final video export."
            ),
        },
        "scene_plan": _build_scene_plan(script, brief),
    }


def write_index(rows: List[Dict[str, Any]]) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def build_index_row(brief: Dict[str, Any], status: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    render_config = resolve_render_config(brief)
    status_render_targets = status.get("render_targets", render_config["targets"])
    if isinstance(status_render_targets, list):
        render_targets_csv = "|".join(str(item).strip() for item in status_render_targets if str(item).strip())
    else:
        render_targets_csv = str(status_render_targets).strip() or render_config["targets_csv"]
    return {
        "job_id": job_id,
        "source_id": str(brief.get("story_id") or brief.get("id", "")).strip(),
        "estado_csv": brief.get("estado", ""),
        "idea_central": brief.get("idea_central", ""),
        "platform": brief.get("plataforma", ""),
        "language": brief.get("idioma", ""),
        "render_targets": render_targets_csv,
        "default_render_target": status.get("default_render_target", render_config["default_target"]),
        "content_orientation": render_config["content_orientation"],
        "brief_created": status["brief_created"],
        "script_generated": status["script_generated"],
        "audio_generated": status["audio_generated"],
        "subtitles_generated": status["subtitles_generated"],
        "visual_manifest_generated": status["visual_manifest_generated"],
        "export_ready": status["export_ready"],
        "last_step": status["last_step"],
        "updated_at": status["updated_at"],
    }
