# AGENTS.md

## Arquitectura rápida

- `main.py`: entrypoint editorial.
- `director.py`: genera `script`, `visual_manifest`, `scene_prompt_pack`, sincroniza `status.json` e índice.
- `story_loader.py`: valida historias Markdown y mueve historias procesadas a `stories/archive/`.
- `voice_registry.py`: registro persistente de voces, selección de voz y estrategia de runtime.
- `wsl/generar_audio_qwen.py`: batch de audio por `job`.
- `wsl/generar_subtitulos.py`: batch de subtítulos por `job`.
- `config.py` y `job_paths.py`: resolución de rutas y contratos físicos.

## Qué no romper

- Ejecutar siempre desde la raíz del repo.
- Mantener imports simples entre módulos del root.
- No mover archivos sin un motivo fuerte.
- No asumir que `data/ideas.csv` es la fuente principal; hoy el flujo por defecto es Markdown.
- No romper la estructura de dataset externo: `stories/`, `jobs/`, `voices/`, `outputs/`, `logs/`, `state/`.
- No cambiar naming de artefactos de job sin revisar `job_paths.py`, `director.py`, audio y subtítulos.

## Convenciones útiles

- `story_id`: identificador estable de la historia fuente.
- `job_id`: ejecución concreta, normalmente `story_id + timestamp`.
- Los jobs se agrupan por bucket: `jobs/<story_bucket>/<job_id>/`.
- Las historias operativas viven en `stories/production/` y deben incluir frontmatter `---` con `id` y `estado`.
- El pipeline solo procesa historias con `estado: pending`.

## Comandos habituales

```bash
python main.py --dry-run
python main.py --story-id h10001
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --dry-run
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --overwrite
bash wsl/run_subs.sh --job-id h10001_20260409_040719
bash wsl/run_reset_audio_state.sh --scope generated --dry-run
```

## Seguridad de cambios

- Antes de tocar documentación, contrasta contra el código real.
- Antes de tocar audio o rutas, revisa `voice_registry.py`, `job_paths.py` y los wrappers de `wsl/`.
- No elimines compatibilidad legacy sin verificar si sigue usándose en `first_existing_path(...)` o en los wrappers.
- Si renombras documentación, actualiza enlaces internos en `README.md` y en `doc/`.
