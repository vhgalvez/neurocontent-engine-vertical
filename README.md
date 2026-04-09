# NeuroContent Engine Vertical

`neurocontent-engine-vertical` prepara artefactos editoriales, audio y subtítulos para vídeos narrativos. El repositorio no renderiza el vídeo final: genera briefs normalizados, guiones, manifiestos visuales, narración `.wav`, subtítulos `.srt` y trazabilidad por `job`.

La entrada principal del pipeline editorial es Markdown. `data/ideas.csv` sigue existiendo como fuente legacy, pero `python main.py` usa `--source markdown` por defecto y procesa historias desde `stories/production/` dentro del dataset configurado.

## Qué hace

- Carga historias Markdown con `story_loader.py`.
- Genera `brief`, `script`, `visual_manifest` y `scene_prompt_pack` con `main.py` y `director.py`.
- Resuelve voces persistidas con `voice_registry.py`.
- Genera audio con Qwen TTS desde los wrappers de `wsl/`.
- Genera subtítulos con WhisperX desde `wsl/run_subs.sh`.

## Estructura general

El código vive en este repo y los datos operativos viven en un dataset externo, normalmente:

```text
video-dataset/
├── stories/
│   ├── draft/
│   ├── production/
│   └── archive/
├── jobs/
├── outputs/
├── logs/
├── state/
└── voices/
```

Cada historia tiene un `story_id` estable, por ejemplo `h10001`. Cada ejecución genera un `job_id` nuevo, por ejemplo `h10001_20260409_040719`. Los jobs se agrupan físicamente por bucket:

```text
jobs/h1000/h10001_20260409_040719/
```

## Quickstart

Desde la raíz del repo:

```bash
python main.py --dry-run
python main.py --story-id h10001
```

Si vas a usar audio en WSL:

```bash
conda activate qwen_gpu
bash wsl/run_design_voice.sh --scope global --voice-name marca_personal_es --description "Voz sobria y profesional." --reference-text "Hola, esta es la voz oficial de la marca."
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --voice-name marca_personal_es --overwrite
bash wsl/run_subs.sh --job-id h10001_20260409_040719
```

## Mapa documental

- [`doc/text_pipeline.md`](doc/text_pipeline.md): flujo editorial, historias Markdown, contratos de entrada y salida.
- [`doc/audio_pipeline.md`](doc/audio_pipeline.md): sistema de voces, Qwen TTS, registro y generación de audio.
- [`doc/subtitles_pipeline.md`](doc/subtitles_pipeline.md): generación de subtítulos, contrato con audio y troubleshooting de WhisperX.
- [`doc/operations.md`](doc/operations.md): operación end-to-end, resets, secuencias recomendadas y validaciones.
- [`AGENTS.md`](AGENTS.md): guía breve para agentes y cambios en el código.

## Comandos básicos

Pipeline editorial:

```bash
python main.py
python main.py --story-id h10001
python main.py --stories-dir /mnt/c/ruta/a/otro/directorio
python main.py --source csv
python main.py --target-audio-minutes 2
python main.py --text-model qwen2.5:7b
```

Reset completo del dataset editorial:

```bash
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --dry-run
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --yes
```

Audio y voces:

```bash
bash wsl/run_design_voice.sh --scope global --voice-name marca_personal_es --description "Voz sobria y profesional." --reference-text "Hola, esta es la voz oficial de la marca."
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --voice-id voice_global_0001 --overwrite
bash wsl/run_generate_audio_from_prompt.sh --voice-name marca_personal_es --text "Prueba rápida de voz persistida."
bash wsl/run_promote_voice_to_clone.sh --voice-name marca_personal_es --overwrite
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Subtítulos:

```bash
bash wsl/run_subs.sh --job-id h10001_20260409_040719
bash wsl/run_subs.sh
```

## Notas importantes

- Ejecuta siempre desde la raíz del repo.
- El source principal ya no es CSV. Documenta y opera pensando en `stories/production/`.
- Audio y subtítulos dependen del dataset externo y de los wrappers de `wsl/`.
- No borres voces manualmente dentro de `voices/`; usa `run_delete_voice.sh`.
- `run_reset_audio_state.sh` limpia audio, subtítulos y/o voces. `reset_dataset.py` resetea además historias, jobs y directorios del dataset.
