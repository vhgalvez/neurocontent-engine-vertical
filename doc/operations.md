# Operación y Flujo Completo

## Propósito

Este documento reúne la operación end-to-end del repositorio sin duplicar la referencia técnica de cada módulo. Sirve para ejecutar el sistema completo, validar resultados, resetear estado y saber en qué orden tocar cada parte.

Para detalles de contrato o CLI de un módulo concreto, usa este documento como mapa operativo y luego baja al documento específico de texto, audio o subtítulos.

## Mapa operativo

La secuencia normal es: historia fuente, pipeline editorial, voz, audio, subtítulos. El resultado de cada fase alimenta la siguiente, y el estado se refleja en `job.json`, `status.json` y los artefactos físicos del dataset.

## Flujo recomendado desde cero

### 1. Preparar el dataset

Confirma que el dataset tenga al menos:

```text
stories/draft
stories/production
stories/archive
jobs
outputs
logs
state
voices
```

Si necesitas un reset completo del dataset:

```bash
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --dry-run
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --yes
```

### 2. Cargar una historia en producción

Coloca un Markdown válido en:

```text
<dataset_root>/stories/production/h10001.md
```

Con `estado: pending`. Si la historia sigue en `draft` o `archive`, `main.py` no la procesará por defecto.

### 3. Ejecutar el flujo editorial

```bash
python main.py --dry-run
python main.py --story-id h10001
```

Eso crea un nuevo `job_id`. A partir de ahí la historia y el job ya no son la misma cosa: la historia es la fuente estable; el job es una ejecución concreta.

### 4. Diseñar o seleccionar una voz

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Si ya tienes una voz, este paso puede sustituirse por elegir `--voice-id`, `--voice-name` o definir `VIDEO_DEFAULT_VOICE_ID`.

### 5. Generar audio

```bash
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --voice-name marca_personal_es --overwrite
```

### 6. Generar subtítulos

```bash
bash wsl/run_subs.sh --job-id h10001_20260409_040719
```

En los ejemplos, `h10001_20260409_040719` es solo un placeholder representativo. Sustitúyelo siempre por el `job_id` real generado en tu ejecución.

## Secuencias operativas útiles

### Editorial

Procesar todo lo pendiente en editorial:

```bash
python main.py
```

Probar una sola historia con otra duración objetivo:

```bash
python main.py --story-id h10001 --target-audio-minutes 2
```

### Audio y voz

Usar una voz global por defecto:

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --overwrite
```

Generar audio de prueba sin job:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name marca_personal_es \
  --text "Esta es una prueba rápida de control."
```

Usar `voice-id` explícito:

```bash
bash wsl/run_audio.sh \
  --job-id h10001_20260409_040719 \
  --voice-id voice_global_0001 \
  --overwrite
```

Usar `voice-name` explícito:

```bash
bash wsl/run_audio.sh \
  --job-id h10001_20260409_040719 \
  --voice-name marca_personal_es \
  --overwrite
```

## Validaciones rápidas

Después del pipeline editorial, confirma que existan:

- `job.json`
- `status.json`
- `source/<job_id>_brief.json`
- `source/<job_id>_script.json`
- `source/<job_id>_visual_manifest.json`

Después de audio, confirma:

- `audio/<job_id>_narration.wav`
- `logs/<job_id>_phase_audio.log`

Después de subtítulos, confirma:

- `subtitles/<job_id>_narration.srt`
- `logs/<job_id>_phase_subtitles.log`

## Reset y limpieza

Reset completo del dataset editorial:

```bash
python reset_dataset.py --dataset-root /mnt/c/ruta/a/video-dataset --yes
```

Reset solo del estado de audio y voces:

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

Inspección sin cambios:

```bash
bash wsl/run_reset_audio_state.sh --scope all --dry-run
```

Limpiar solo audio, subtítulos y logs derivados:

```bash
bash wsl/run_reset_audio_state.sh --scope generated --confirm
```

Limpiar solo voices registry y referencias de voz:

```bash
bash wsl/run_reset_audio_state.sh --scope voices --confirm
```

## Problemas típicos

Si el editorial no procesa nada, revisa primero `estado: pending` y que el archivo esté en `stories/production/`. Si audio falla, revisa `QWEN_PYTHON`, el entorno `qwen_gpu` y que el `job` tenga ya `script.json`. Si subtítulos fallan, confirma antes que existe `audio/<job_id>_narration.wav`.

Si una voz no se deja borrar, no fuerces el filesystem: el bloqueo suele indicar que sigue referenciada en algún `job`. Si un reset de audio parece demasiado destructivo, usa siempre `--dry-run` antes de `--confirm`.

## Qué mirar según la tarea

- Editorial y Markdown: `doc/text_pipeline.md`
- Voces y audio: `doc/audio_pipeline.md`
- WhisperX y subtítulos: `doc/subtitles_pipeline.md`
