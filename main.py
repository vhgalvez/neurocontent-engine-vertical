import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

from config import (
    DATA_FILE,
    OVERWRITE_MANIFEST,
    OVERWRITE_SCRIPT,
    configure_runtime,
    get_text_model,
    get_runtime_paths,
)
from story_loader import load_all_stories
from story_loader import archive_story_file, validate_dataset_story_index
from director import (
    OllamaError,
    build_index_row,
    build_visual_manifest,
    ensure_job_metadata,
    generate_scene_prompt_pack,
    generate_script,
    get_job_paths,
    safe_read_json,
    safe_write_json,
    sync_status_with_files,
    resolve_render_config,
    update_job_manifest_status,
    update_status,
    validate_script_data,
    write_index,
)
from job_paths import (
    build_unique_story_job_id,
    ensure_dataset_structure,
    first_existing_path,
    pad_job_id,
    pad_story_id,
)

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
        help="Alias legacy de --story-id. Filtra historias por story_id. Repetible.",
    )
    parser.add_argument(
        "--story-id",
        action="append",
        dest="story_ids",
        help="Procesa solo las historias indicadas por story_id. Repetible.",
    )
    parser.add_argument(
        "--source",
        choices=["markdown", "csv"],
        default="markdown",
        help="Fuente principal de historias: markdown (por defecto) o csv (legacy)",
    )
    parser.add_argument(
        "--stories-dir",
        help="Override del directorio de historias activas. Por defecto usa dataset/stories/production.",
    )
    parser.add_argument(
        "--text-model",
        help="Override del modelo generador de texto para esta ejecucion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valida el dataset y muestra que historias procesaria sin ejecutar el pipeline.",
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


def load_briefs_csv() -> List[Dict[str, Any]]:
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


def build_execution_job_id(brief: Dict[str, Any]) -> str:
    story_id = str(brief.get("story_id") or brief.get("id") or "").strip()
    if not story_id:
        raise ValueError("El brief no contiene story_id o id utilizable.")
    runtime = get_runtime_paths()
    return build_unique_story_job_id(story_id, runtime.jobs_root)


def resolve_pipeline_job_id(brief: Dict[str, Any]) -> str:
    explicit_job_id = str(brief.get("job_id") or "").strip()
    if explicit_job_id:
        return explicit_job_id
    if brief.get("story_file") or brief.get("story_id"):
        return build_execution_job_id(brief)
    return pad_job_id(brief.get("id"))


def validate_dataset_runtime(runtime) -> None:
    if not runtime.dataset_root.exists():
        raise FileNotFoundError(
            f"No existe el directorio de dataset configurado: {runtime.dataset_root}"
        )


def resolve_markdown_stories_dir(args: argparse.Namespace, runtime) -> Path:
    return Path(args.stories_dir) if args.stories_dir else runtime.stories_production_dir


def load_markdown_briefs(args: argparse.Namespace, runtime) -> List[Dict[str, Any]]:
    validate_dataset_story_index(runtime.stories_root)
    stories_dir = resolve_markdown_stories_dir(args, runtime)
    return load_all_stories(stories_dir)


def validate_requested_story_ids(
    all_briefs: List[Dict[str, Any]],
    selected_story_ids: set[str],
) -> None:
    if not selected_story_ids:
        return

    available_story_ids = {
        pad_story_id(brief.get("metadata", {}).get("id", brief.get("id")))
        for brief in all_briefs
    }
    missing_story_ids = sorted(selected_story_ids - available_story_ids)
    if missing_story_ids:
        raise FileNotFoundError(
            "No existe la historia solicitada en stories/production: "
            f"{', '.join(missing_story_ids)}"
        )


def select_pending_markdown_briefs(
    all_briefs: List[Dict[str, Any]],
    selected_story_ids: set[str],
) -> List[Dict[str, Any]]:
    pending_briefs = [
        brief
        for brief in all_briefs
        if brief.get("metadata", {}).get("estado", brief.get("estado", "")).lower() == "pending"
    ]
    if selected_story_ids:
        pending_briefs = [
            brief
            for brief in pending_briefs
            if pad_story_id(brief.get("metadata", {}).get("id", brief.get("id"))) in selected_story_ids
        ]
    return pending_briefs


def archive_processed_story(brief: Dict[str, Any], runtime) -> Path:
    story_path = brief.get("story_file")
    if not story_path:
        raise ValueError("El brief no contiene story_file para archivar la historia.")
    return archive_story_file(story_path, runtime.stories_archive_dir, archive_state="archived")


def process_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    job_id = resolve_pipeline_job_id(brief)
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
        last_step="brief_synced_from_source",
    )

    script = _load_or_generate_script(brief, paths)
    manifest = _load_or_generate_manifest(brief, script, paths)
    generate_scene_prompt_pack(brief, script, manifest, paths)

    status = sync_status_with_files(paths)
    return build_index_row(brief, status, job_id)


def build_error_index_row(brief: Dict[str, Any], message: str) -> Dict[str, Any]:
    job_id = resolve_pipeline_job_id(brief)
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
    configure_runtime(
        dataset_root=args.dataset_root,
        jobs_root=args.jobs_root,
        text_model=args.text_model,
    )
    runtime = get_runtime_paths()
    validate_dataset_runtime(runtime)
    ensure_dataset_structure(runtime)

    print(f"Dataset root: {runtime.dataset_root}")
    print(f"Dataset name: {runtime.dataset_name}")
    print(f"Jobs root: {runtime.jobs_root}")
    print(f"Fuente de historias: {args.source}")
    print(f"Modelo de texto activo: {get_text_model()}")

    if args.source == "markdown":
        print(f"Stories production: {resolve_markdown_stories_dir(args, runtime)}")
        all_briefs = load_markdown_briefs(args, runtime)
    else:
        all_briefs = load_briefs_csv()

    selected_story_ids = {
        pad_story_id(story_id)
        for story_id in [*(args.story_ids or []), *(args.job_ids or [])]
    }
    if args.source == "markdown":
        validate_requested_story_ids(all_briefs, selected_story_ids)
    briefs = (
        select_pending_markdown_briefs(all_briefs, selected_story_ids)
        if args.source == "markdown"
        else [brief for brief in all_briefs if brief.get("estado", "").lower() == "pending"]
    )

    if not briefs:
        if args.source == "markdown":
            print("No hay historias pending en stories/production para procesar.")
            return
        print("No hay briefs pendientes. Reconstruyendo solo data/index.csv como indice derivado.")
        if args.source == "csv":
            write_index(build_derived_index(all_briefs))
        else:
            print("(Modo Markdown: índice derivado no implementado aún)")
        return

    if args.dry_run:
        print("DRY RUN: historias pending detectadas:")
        for brief in briefs:
            meta = brief.get("metadata", brief)
            story_id = pad_story_id(meta.get("id", brief.get("id")))
            story_file = brief.get("story_file", "")
            planned_job_id = build_execution_job_id({"story_id": story_id, "story_file": story_file})
            print(f"- story_id={story_id} -> job_id={planned_job_id} -> file={story_file}")
        print("Dry run completado. No se genero ningun job ni se movio ninguna historia.")
        return

    for position, brief in enumerate(briefs, start=1):
        # Normalizar acceso a campos para Markdown o CSV
        meta = brief.get("metadata", brief)
        title = meta.get("idea_central", meta.get("title", f"brief_{position}"))
        print(f"[{position}/{len(briefs)}] Procesando: {title}")

        # Adaptar brief para el pipeline (debe ser un dict plano)
        pipeline_brief = dict(meta)
        story_id = pad_story_id(meta.get("id", pipeline_brief.get("id")))
        pipeline_brief["id"] = story_id
        pipeline_brief["story_id"] = story_id
        if brief.get("story_file"):
            pipeline_brief["story_file"] = str(Path(brief["story_file"]).as_posix())
        pipeline_brief["job_id"] = build_execution_job_id(pipeline_brief)
        # Añadir campos de cuerpo si existen (Markdown)
        for k in ("title", "hook", "historia", "cta", "visual_notes", "prohibido"):
            if k in brief:
                pipeline_brief[k] = brief[k]

        try:
            process_brief(pipeline_brief)
            update_job_manifest_status(get_job_paths(pipeline_brief["job_id"]), "done")
            if args.source == "markdown":
                archived_path = archive_processed_story(pipeline_brief, runtime)
                print(f"Historia archivada en: {archived_path}")
        except OllamaError as exc:
            print(f"ERROR Ollama: {exc}")
            build_error_index_row(pipeline_brief, str(exc))
            update_job_manifest_status(get_job_paths(pipeline_brief["job_id"]), "error")
        except Exception as exc:
            print(f"ERROR inesperado: {exc}")
            build_error_index_row(pipeline_brief, f"Error inesperado: {exc}")
            update_job_manifest_status(get_job_paths(pipeline_brief["job_id"]), "error")

    if args.source == "csv":
        write_index(build_derived_index(all_briefs))
    print("Pipeline editorial completado.")


if __name__ == "__main__":
    main()
