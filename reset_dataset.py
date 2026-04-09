import argparse
import shutil
from pathlib import Path

from config import configure_runtime, get_runtime_paths
from job_paths import ensure_dataset_structure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resetea un dataset de forma controlada.")
    parser.add_argument("--dataset-root", help="Override para VIDEO_DATASET_ROOT.")
    parser.add_argument("--jobs-root", help="Override para VIDEO_JOBS_ROOT.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra que se borraria sin aplicar cambios.")
    parser.add_argument("--yes", action="store_true", help="Confirma el reseteo sin pedir validacion adicional.")
    return parser.parse_args()


def build_reset_targets(runtime) -> list[Path]:
    return [
        runtime.stories_draft_dir,
        runtime.stories_production_dir,
        runtime.stories_archive_dir,
        runtime.jobs_root,
        runtime.outputs_root,
        runtime.logs_root,
        runtime.state_root,
    ]


def describe_targets(paths: list[Path]) -> None:
    print("Directorios afectados:")
    for path in paths:
        print(f"- {path}")


def reset_directory(path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] limpiaria: {path}")
        return

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    configure_runtime(dataset_root=args.dataset_root, jobs_root=args.jobs_root)
    runtime = get_runtime_paths()

    runtime.dataset_root.mkdir(parents=True, exist_ok=True)
    targets = build_reset_targets(runtime)

    print(f"Dataset root: {runtime.dataset_root}")
    describe_targets(targets)

    if args.dry_run:
        for path in targets:
            reset_directory(path, dry_run=True)
        print("Dry run completado. No se aplicaron cambios.")
        return 0

    if not args.yes:
        print("Operacion cancelada. Usa --yes para confirmar el reseteo.")
        return 1

    for path in targets:
        reset_directory(path, dry_run=False)

    ensure_dataset_structure(runtime)
    print("Dataset reseteado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
