# Pipeline de Texto y Editorial

## Propósito

Este módulo convierte historias fuente en artefactos editoriales listos para producción. La entrada principal son archivos Markdown en el dataset; la salida son carpetas de `job` con `brief`, `script`, `visual_manifest` y `scene_prompt_pack`.

El flujo vive sobre todo en `main.py`, `story_loader.py`, `director.py`, `prompts.py`, `config.py` y `job_paths.py`. `data/ideas.csv` sigue soportado, pero solo como fuente legacy.

## Componentes implicados

- `main.py`: selecciona historias, configura runtime y orquesta la ejecución.
- `story_loader.py`: valida frontmatter, secciones obligatorias y estados editoriales.
- `director.py`: genera guion, manifiesto visual, scene prompt pack e índice derivado.
- `prompts.py`: prompts usados para generar y reescribir el contenido.
- `config.py`: resuelve modelo de texto y duración objetivo.
- `job_paths.py`: construye rutas de dataset y nombres de artefactos.

## Entrada principal: historias Markdown

Por defecto `python main.py` lee historias desde:

```text
<dataset_root>/stories/production/
```

Cada archivo debe cumplir dos contratos. Primero, el nombre del archivo debe coincidir con `id`. Segundo, el cuerpo debe tener las secciones mínimas que espera `story_loader.py`.

Ejemplo mínimo válido:

```md
---
id: h10001
estado: pending
idioma: es
plataforma: tiktok
formato: video_corto
duracion_seg: 90
objetivo: atraer
tono: storytelling_intimo
ritmo: medio
estilo_narracion: narrativo
tipo_cierre: reflexivo
render_targets: vertical|horizontal
default_render_target: vertical
target_aspect_ratio: 9:16|16:9
---

# La decisión que lo cambió todo

## Hook

Una sola llamada cambió por completo su vida.

## Historia

Texto principal de la historia.

## CTA

¿Qué habrías hecho tú?

## Visual Notes

Notas visuales opcionales.

## Prohibido

Límites opcionales del guion.
```

Estados válidos:

- `draft`
- `pending`
- `processing`
- `done`
- `archived`
- `error`

Solo se procesan historias con `estado: pending`. Cuando una historia Markdown termina bien, `main.py` la mueve a `stories/archive/` y actualiza su estado a `archived`.

## Flujo paso a paso

1. `main.py` resuelve `dataset_root`, `jobs_root`, modelo de texto y duración objetivo.
2. `story_loader.py` valida el índice de historias y carga los `.md` desde `stories/production/`.
3. `main.py` filtra por `story_id` si pasas `--story-id` o `--job-id` como alias legacy.
4. Para cada historia pendiente se crea un `job_id` nuevo con timestamp.
5. `director.py` sincroniza `brief.json`, genera o reutiliza `script.json` y `visual_manifest.json`.
6. `director.py` genera además `scene_prompt_pack.json` y `scene_prompt_pack.md`.
7. Se actualizan `job.json`, `status.json` e `index.csv`.
8. Si el source fue Markdown y no hubo error, la historia fuente se archiva.

## Estructura de salida

Cada ejecución se escribe dentro del dataset externo:

```text
jobs/<story_bucket>/<job_id>/
├── job.json
├── status.json
├── source/
│   ├── <job_id>_brief.json
│   ├── <job_id>_script.json
│   ├── <job_id>_visual_manifest.json
│   ├── <job_id>_scene_prompt_pack.json
│   ├── <job_id>_scene_prompt_pack.md
│   └── <job_id>_rendered_comfy_workflow.json
├── audio/
├── subtitles/
└── logs/
```

`job.json` es el contrato estable del job. `status.json` es el estado operativo. `scene_prompt_pack.md` es una salida humana para producción visual manual; no sustituye a `scene_prompt_pack.json`.

## Comandos reales

Procesar todas las historias pendientes:

```bash
python main.py
```

Validar sin ejecutar:

```bash
python main.py --dry-run
```

Procesar una historia concreta:

```bash
python main.py --story-id h10001
```

Procesar varias historias:

```bash
python main.py --story-id h10001 --story-id h10002
```

Usar un directorio alternativo de historias activas:

```bash
python main.py --stories-dir /mnt/c/ruta/a/dataset/stories/production
```

Cambiar el modelo de texto para una sola ejecución:

```bash
python main.py --story-id h10001 --text-model qwen2.5:7b
```

Orientar la longitud del guion narrado:

```bash
python main.py --story-id h10001 --target-audio-minutes 2
```

Usar el modo CSV legacy:

```bash
python main.py --source csv
```

## Variables y resolución de runtime

`config.py` y `job_paths.py` resuelven runtime con esta prioridad:

1. argumentos CLI
2. variables de entorno
3. valores por defecto

Variables útiles:

- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`
- `DATASET_ROOT`
- `TEXT_MODEL`
- `TARGET_AUDIO_MINUTES`

La duración objetivo solo orienta el texto. No cambia por sí sola la lógica de audio ni de subtítulos.

## Contratos con otros módulos

El módulo editorial entrega al módulo de audio dos piezas críticas: `script.json` y `job.json`. Audio usa esos artefactos para decidir qué texto sintetizar, dónde escribir el `.wav` y qué voz resolver. El módulo de subtítulos, a su vez, depende de que el audio ya exista en `audio/<job_id>_narration.wav` o en una ruta legacy compatible.

## Notas importantes

`story_loader.py` normaliza el Markdown a un schema compatible con el flujo histórico de `director.py`. Eso permite que el sistema siga construyendo briefs y manifests con el contrato anterior, pero la fuente editorial de verdad ahora es el Markdown del dataset.

El bucket físico del job se deriva del `story_id`. Por ejemplo, `h10001` cae en `h1000`. Eso ordena el filesystem sin cambiar el modelo mental: una historia puede tener múltiples jobs.

## Troubleshooting básico

Si `main.py` dice que no existe una historia pedida, revisa que esté en `stories/production/` y no en `stories/draft/` o `stories/archive/`. Si el error habla de frontmatter incompleto o de secciones vacías, corrige primero el Markdown; `story_loader.py` falla antes de llamar a generación.

Si el pipeline parece ignorar una historia, casi siempre es porque `estado` no es `pending`. Si necesitas reconstruir el dataset completo para pruebas, usa:

```bash
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --dry-run
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --yes
```
