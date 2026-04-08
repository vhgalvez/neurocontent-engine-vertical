import argparse
import csv
from typing import Any, Dict, List

from config import (
    DATA_FILE,
    OVERWRITE_MANIFEST,
    OVERWRITE_SCRIPT,
    configure_runtime,
    get_runtime_paths,
)
from director import (
    OllamaError,
    build_index_row,
    build_visual_manifest,
    ensure_job_metadata,
    generate_scene_prompt_pack,
    generate_script,
    get_job_paths,
    pad_job_id,
    safe_read_json,
    safe_write_json,
    sync_status_with_files,
    resolve_render_config,
    update_status,
    validate_script_data,
    write_index,
)
from job_paths import first_existing_path

REQUIRED_COLUMNS = {
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
}

OPTIONAL_RENDER_COLUMNS = {
    "render_targets",
    "default_render_target",
    "content_orientation",
    "target_aspect_ratio",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline editorial de NeuroContent Engine.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument(
        "--job-id",
        action="append",
        dest="job_ids",
        help="Procesa solo los jobs indicados. Repetible.",
    )
    return parser.parse_args()


def _clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in row.items()
    }
    for key in OPTIONAL_RENDER_COLUMNS:
        cleaned.setdefault(key, "")
    return cleaned


def _validate_headers(fieldnames: List[str] | None) -> None:
    if not fieldnames:
        raise ValueError(f"El archivo CSV está vacío o no tiene cabeceras: {DATA_FILE}")

    missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Faltan columnas obligatorias en {DATA_FILE}: {missing_text}")


def load_briefs() -> List[Dict[str, Any]]:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"No existe el archivo de briefs: {DATA_FILE}. "
            "Crea data\\ideas.csv antes de ejecutar python main.py."
        )

    briefs: List[Dict[str, Any]] = []

    with DATA_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        _validate_headers(reader.fieldnames)

        for row in reader:
            briefs.append(_clean_row(row))

    return briefs


def _load_or_generate_script(brief: Dict[str, Any], paths) -> Dict[str, Any]:
    script_input = first_existing_path(paths.script, paths.legacy_script_candidates)
    if script_input.exists() and not OVERWRITE_SCRIPT:
        update_status(paths.status, script_generated=True, last_step="script_reused")
        existing_script = safe_read_json(script_input, default={}) or {}
        if not existing_script:
            raise ValueError(f"script.json vacio o invalido para job {paths.job_id}")
        validate_script_data(existing_script)
        if script_input != paths.script:
            safe_write_json(paths.script, existing_script)
        return existing_script

    script = generate_script(brief)
    safe_write_json(paths.script, script)
    update_status(paths.status, script_generated=True, last_step="script_generated")
    return script


def _load_or_generate_manifest(
    brief: Dict[str, Any],
    script: Dict[str, Any],
    paths,
) -> Dict[str, Any]:
    manifest_input = first_existing_path(paths.manifest, paths.legacy_manifest_candidates)
    if manifest_input.exists() and not OVERWRITE_MANIFEST:
        update_status(paths.status, visual_manifest_generated=True, last_step="manifest_reused")
        existing_manifest = safe_read_json(manifest_input, default={}) or {}
        if not existing_manifest:
            raise ValueError(f"visual_manifest.json vacio o invalido para job {paths.job_id}")
        manifest_needs_refresh = any(
            key not in existing_manifest
            for key in [
                "render_targets",
                "default_render_target",
                "content_orientation",
                "target_aspect_ratios",
                "render_profiles",
            ]
        )
        if "aspect_ratio" in existing_manifest:
            manifest_needs_refresh = True
        if manifest_needs_refresh:
            existing_manifest = build_visual_manifest(
                brief=brief,
                script=script,
                job_id=paths.job_id,
                audio_path=paths.audio,
                subtitles_path=paths.subtitles,
            )
        if manifest_input != paths.manifest:
            safe_write_json(paths.manifest, existing_manifest)
        elif manifest_needs_refresh:
            safe_write_json(paths.manifest, existing_manifest)
        return existing_manifest

    manifest = build_visual_manifest(
        brief=brief,
        script=script,
        job_id=paths.job_id,
        audio_path=paths.audio,
        subtitles_path=paths.subtitles,
    )
    safe_write_json(paths.manifest, manifest)
    update_status(
        paths.status,
        visual_manifest_generated=True,
        last_step="visual_manifest_generated",
    )
    return manifest


def process_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    job_id = pad_job_id(brief.get("id"))
    paths = get_job_paths(job_id)
    render_config = resolve_render_config(brief)

    ensure_job_metadata(paths, brief)
    safe_write_json(paths.brief, brief)
    update_status(
        paths.status,
        brief_created=True,
        render_targets=render_config["targets"],
        default_render_target=render_config["default_target"],
        render_vertical_requested="vertical" in render_config["targets"],
        render_horizontal_requested="horizontal" in render_config["targets"],
        render_vertical_ready=False,
        render_horizontal_ready=False,
        last_step="brief_synced_from_csv",
    )

    script = _load_or_generate_script(brief, paths)
    manifest = _load_or_generate_manifest(brief, script, paths)
    generate_scene_prompt_pack(brief, script, manifest, paths)

    status = sync_status_with_files(paths)
    return build_index_row(brief, status, job_id)


def build_error_index_row(brief: Dict[str, Any], message: str) -> Dict[str, Any]:
    job_id = pad_job_id(brief.get("id"))
    paths = get_job_paths(job_id)
    render_config = resolve_render_config(brief)

    ensure_job_metadata(paths, brief)
    safe_write_json(paths.brief, brief)
    status = update_status(
        paths.status,
        brief_created=True,
        script_generated=first_existing_path(paths.script, paths.legacy_script_candidates).exists(),
        visual_manifest_generated=first_existing_path(paths.manifest, paths.legacy_manifest_candidates).exists(),
        scene_prompt_pack_generated=paths.scene_prompt_pack.exists() and paths.scene_prompt_pack_markdown.exists(),
        scene_prompt_pack_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack) if paths.scene_prompt_pack.exists() else "",
        scene_prompt_pack_markdown_file=paths.runtime.to_dataset_relative(paths.scene_prompt_pack_markdown) if paths.scene_prompt_pack_markdown.exists() else "",
        render_targets=render_config["targets"],
        default_render_target=render_config["default_target"],
        render_vertical_requested="vertical" in render_config["targets"],
        render_horizontal_requested="horizontal" in render_config["targets"],
        render_vertical_ready=False,
        render_horizontal_ready=False,
        last_step=f"error: {message}",
    )
    return build_index_row(brief, status, job_id)


def build_derived_index(all_briefs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index_rows: List[Dict[str, Any]] = []

    for brief in all_briefs:
        job_id = pad_job_id(brief.get("id"))
        paths = get_job_paths(job_id)
        has_job_material = any(
            path.exists()
            for path in [
                first_existing_path(paths.brief, paths.legacy_brief_candidates),
                first_existing_path(paths.script, paths.legacy_script_candidates),
                first_existing_path(paths.manifest, paths.legacy_manifest_candidates),
                first_existing_path(paths.audio, paths.legacy_audio_candidates),
                first_existing_path(paths.subtitles, paths.legacy_subtitles_candidates),
            ]
        )

        if not has_job_material and brief.get("estado", "").lower() != "pending":
            continue
        if brief.get("estado", "").lower() == "pending" and not first_existing_path(paths.brief, paths.legacy_brief_candidates).exists():
            continue

        status = sync_status_with_files(paths)
        index_rows.append(build_index_row(brief, status, job_id))

    return index_rows


def main() -> None:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    runtime = get_runtime_paths()

    print(f"Dataset root: {runtime.dataset_root}")
    print(f"Jobs root: {runtime.jobs_root}")
    print("Cargando briefs pendientes...")

    all_briefs = load_briefs()
    selected_job_ids = {pad_job_id(job_id) for job_id in args.job_ids or []}
    briefs = [brief for brief in all_briefs if brief.get("estado", "").lower() == "pending"]
    if selected_job_ids:
        briefs = [brief for brief in briefs if pad_job_id(brief.get("id")) in selected_job_ids]

    if not briefs:
        print("No hay briefs pendientes. Reconstruyendo solo data/index.csv como indice derivado.")
        write_index(build_derived_index(all_briefs))
        return

    for position, brief in enumerate(briefs, start=1):
        title = brief.get("idea_central", f"brief_{position}")
        print(f"[{position}/{len(briefs)}] Procesando: {title}")

        try:
            process_brief(brief)
        except OllamaError as exc:
            print(f"ERROR Ollama: {exc}")
            build_error_index_row(brief, str(exc))
        except Exception as exc:
            print(f"ERROR inesperado: {exc}")
            build_error_index_row(brief, f"Error inesperado: {exc}")

    write_index(build_derived_index(all_briefs))
    print("Pipeline editorial completado.")


if __name__ == "__main__":
    main()
