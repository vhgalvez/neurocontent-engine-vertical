import argparse
import shutil
import sys
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import configure_runtime, get_runtime_paths  # noqa: E402
from director import update_status  # noqa: E402
from job_paths import build_job_paths  # noqa: E402
from voice_registry import initialize_empty_voice_index, load_job_document, save_job_document  # noqa: E402


def log(message: str) -> None:
    print(message, flush=True)


def ensure_within(parent: Path, child: Path) -> None:
    parent_resolved = parent.resolve()
    child_resolved = child.resolve()
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise RuntimeError(f"Ruta fuera del alcance permitido: {child_resolved} no cuelga de {parent_resolved}") from exc


def remove_path(path: Path, *, dry_run: bool) -> bool:
    if not path.exists():
        return False
    if dry_run:
        return True
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def iter_job_ids(jobs_root: Path) -> list[str]:
    if not jobs_root.exists():
        return []
    return sorted(path.name for path in jobs_root.iterdir() if path.is_dir())


def clear_generated_state(job_paths, *, dry_run: bool) -> dict[str, int]:
    removed_audio_files = 0
    removed_subtitle_files = 0
    removed_logs = 0
    document_changed = False

    candidates = [job_paths.audio, *job_paths.legacy_audio_candidates]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if remove_path(candidate, dry_run=dry_run):
            removed_audio_files += 1

    candidates = [job_paths.subtitles, *job_paths.legacy_subtitles_candidates]
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if remove_path(candidate, dry_run=dry_run):
            removed_subtitle_files += 1

    if job_paths.logs_dir.exists():
        for child in job_paths.logs_dir.iterdir():
            if "_phase_audio" in child.name or "_phase_subtitles" in child.name:
                if remove_path(child, dry_run=dry_run):
                    removed_logs += 1

    document = load_job_document(job_paths)
    artifacts = document.setdefault("artifacts", {})
    if artifacts.pop("audio", None) is not None:
        document_changed = True
    if artifacts.pop("subtitles", None) is not None:
        document_changed = True
    if document.get("audio_synthesis"):
        document["audio_synthesis"] = {}
        document_changed = True
    if document_changed and not dry_run:
        save_job_document(job_paths, document)

    update_status(
        job_paths.status,
        audio_generated=False,
        subtitles_generated=False,
        tts_strategy_requested="",
        tts_strategy_used="",
        tts_fallback_used=False,
        tts_fallback_reason="",
        audio_file="",
        audio_generated_at="",
        last_step="reset_generated_state" if not dry_run else "reset_generated_state_dry_run",
    )
    return {
        "removed_audio_files": removed_audio_files,
        "removed_subtitle_files": removed_subtitle_files,
        "removed_logs": removed_logs,
        "job_documents_updated": 1 if document_changed else 0,
    }


def clear_voice_state(job_paths, *, dry_run: bool) -> dict[str, int]:
    document = load_job_document(job_paths)
    document_changed = False
    if document.get("voice"):
        document["voice"] = {}
        document_changed = True
    if document.get("audio_synthesis"):
        document["audio_synthesis"] = {}
        document_changed = True
    if document_changed and not dry_run:
        save_job_document(job_paths, document)

    update_status(
        job_paths.status,
        voice_id="",
        voice_scope="",
        voice_source="",
        voice_name="",
        voice_selection_mode="",
        voice_model_name="",
        voice_reference_file="",
        voice_mode="",
        tts_strategy_requested="",
        tts_strategy_used="",
        tts_fallback_used=False,
        tts_fallback_reason="",
        last_step="reset_voice_state" if not dry_run else "reset_voice_state_dry_run",
    )
    return {"job_documents_updated": 1 if document_changed else 0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resetea el estado operativo de audio y voces sin borrar codigo, modelos ni fuentes editoriales."
    )
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument(
        "--scope",
        choices=["voices", "generated", "all"],
        default="all",
        help="voices: limpia registry y referencias de voz. generated: limpia audio/subtitulos/logs derivados. all: ambos.",
    )
    parser.add_argument("--confirm", action="store_true", help="Confirma la ejecucion real del reset.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra que se limpiaria sin aplicar cambios.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run and not args.confirm:
        raise SystemExit("ERROR: este reset requiere --confirm. Usa --dry-run para inspeccionar sin cambios.")

    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)

    try:
        runtime = get_runtime_paths()
        ensure_within(runtime.dataset_root, runtime.jobs_root)
        ensure_within(runtime.dataset_root, runtime.voices_root)

        job_ids = iter_job_ids(runtime.jobs_root)
        summary = {
            "jobs_processed": len(job_ids),
            "removed_audio_files": 0,
            "removed_subtitle_files": 0,
            "removed_logs": 0,
            "job_documents_updated": 0,
            "removed_voice_entries": 0,
            "removed_voice_filesystem_entries": 0,
        }

        if args.scope in {"generated", "all"}:
            for job_id in job_ids:
                job_paths = build_job_paths(job_id, runtime)
                stats = clear_generated_state(job_paths, dry_run=args.dry_run)
                for key, value in stats.items():
                    summary[key] += value

        if args.scope in {"voices", "all"}:
            for job_id in job_ids:
                job_paths = build_job_paths(job_id, runtime)
                stats = clear_voice_state(job_paths, dry_run=args.dry_run)
                for key, value in stats.items():
                    summary[key] += value

            if runtime.voices_root.exists():
                for child in runtime.voices_root.iterdir():
                    summary["removed_voice_filesystem_entries"] += 1
                    if not args.dry_run:
                        if child.is_dir():
                            shutil.rmtree(child)
                        else:
                            child.unlink()
            if not args.dry_run:
                initialize_empty_voice_index(runtime)
            summary["removed_voice_entries"] = summary["removed_voice_filesystem_entries"]

        mode = "DRY-RUN" if args.dry_run else "APPLIED"
        log(f"[reset_audio_state] Mode: {mode}")
        log(f"[reset_audio_state] Scope: {args.scope}")
        log(f"[reset_audio_state] Dataset root: {runtime.dataset_root}")
        log(f"[reset_audio_state] Jobs root: {runtime.jobs_root}")
        log(f"[reset_audio_state] Jobs procesados: {summary['jobs_processed']}")
        log(f"[reset_audio_state] Audios eliminados: {summary['removed_audio_files']}")
        log(f"[reset_audio_state] Subtitulos eliminados: {summary['removed_subtitle_files']}")
        log(f"[reset_audio_state] Logs eliminados: {summary['removed_logs']}")
        log(f"[reset_audio_state] Job documents actualizados: {summary['job_documents_updated']}")
        if args.scope in {"voices", "all"}:
            log(f"[reset_audio_state] Entradas fisicas de voices eliminadas: {summary['removed_voice_filesystem_entries']}")
            log(f"[reset_audio_state] voices_index.json {'recreado' if not args.dry_run else 'seria recreado'}: {runtime.voices_index_file}")
    except Exception as exc:
        log(f"[reset_audio_state] Error: {exc}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
