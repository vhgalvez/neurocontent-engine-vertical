# NeuroContent Engine

`neurocontent-engine` es un pipeline editorial y de preproducción para short-form content. El repositorio genera y mantiene artefactos por job, pero la raíz principal de esos artefactos ya no vive dentro del repo: vive en el dataset externo.

El contrato editorial ahora soporta targets de render explícitos:

- `vertical`
- `horizontal`
- `vertical|horizontal`

## Estado operativo y mapa documental

La documentación del proyecto se ha auditado y reorganizado para reflejar el estado real del sistema después de las correcciones recientes en:

- entorno funcional de Qwen3-TTS sobre WSL2
- wrappers Bash que usan `QWEN_PYTHON`
- registro de voces y unicidad de `voice_name`
- borrado consistente de voces
- validación fuerte de `voices_index.json`

Punto de entrada recomendado para entender el sistema:

- este `README.md`: visión general del repositorio, estructura de jobs y flujo operativo principal
- `wsl/VOICE_SYSTEM_GUIDE.md`: guía técnica extensa del sistema de voces, registry, validaciones y borrado
- `wsl/errores.md`: troubleshooting operativo y estado verificado del entorno Qwen3-TTS en WSL2
- `wsl/AUDIO_GUIDE.md`: guía corta de arranque, comandos reales y navegación documental

Si estás trabajando en audio y voces, la lectura recomendada es:

1. `README.md`
2. `wsl/VOICE_SYSTEM_GUIDE.md`
3. `wsl/errores.md`
4. `wsl/AUDIO_GUIDE.md`

Checklist mínimo recomendado antes de tocar audio y voces:

```bash
conda activate qwen_gpu
which python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

## Dataset y resolución de rutas

Resolución de prioridad:

1. argumentos CLI
2. variables de entorno
3. fallback por defecto:
   `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset`

Variables soportadas:

- `VIDEO_DATASET_ROOT`
- `VIDEO_JOBS_ROOT`
- `VIDEO_DEFAULT_VOICE_ID`

Defaults efectivos:

- dataset root: `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset`
- jobs root: `/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs`

El repo mantiene compatibilidad razonable de lectura con `jobs/<job_id>/` dentro del propio proyecto, pero la escritura nueva apunta al dataset externo.

## Nueva estructura de jobs





```text
video-dataset/
├── jobs/
│   └── 000001/
│       ├── job.json
│       ├── status.json
│       ├── source/
│       │   ├── 000001_brief.json
│       │   ├── 000001_script.json
│       │   ├── 000001_visual_manifest.json
│       │   ├── 000001_scene_prompt_pack.json
│       │   ├── 000001_scene_prompt_pack.md
│       │   └── 000001_rendered_comfy_workflow.json
│       ├── audio/
│       │   └── 000001_narration.wav
│       ├── subtitles/
│       │   └── 000001_narration.srt
│       └── logs/
│           ├── 000001_phase_editorial.log
│           ├── 000001_phase_audio.log
│           └── 000001_phase_subtitles.log
└── voices/
    ├── voice_global_0001/
    │   ├── voice.json
    │   ├── reference.wav
    │   ├── reference.txt
    │   └── voice_clone_prompt.json
    └── voices_index.json
```

## Naming por `job_id`

Todos los artefactos nuevos del job usan el mismo `job_id` en el nombre:

- `jobs/000001/source/000001_brief.json`
- `jobs/000001/source/000001_script.json`
- `jobs/000001/source/000001_visual_manifest.json`
- `jobs/000001/source/000001_scene_prompt_pack.json`
- `jobs/000001/source/000001_scene_prompt_pack.md`
- `jobs/000001/source/000001_rendered_comfy_workflow.json`
- `jobs/000001/audio/000001_narration.wav`
- `jobs/000001/subtitles/000001_narration.srt`
- `jobs/000001/logs/000001_phase_editorial.log`

`job.json` y `status.json` mantienen nombre fijo porque son el contrato estable del directorio del job.

## Render targets editoriales

El CSV `data/ideas.csv` acepta cuatro columnas nuevas:

- `render_targets`
- `default_render_target`
- `content_orientation`
- `target_aspect_ratio`

Valores soportados:

- `render_targets`: `vertical`, `horizontal`, `vertical|horizontal`
- `default_render_target`: `vertical`, `horizontal`
- `content_orientation`: `portrait`, `landscape`, `multi`
- `target_aspect_ratio`: `9:16`, `16:9`, `9:16|16:9`

Compatibilidad con CSV antiguos:

- si esas columnas no existen, el pipeline sigue funcionando
- defaults efectivos: `render_targets=vertical`, `default_render_target=vertical`, `content_orientation=portrait`, `target_aspect_ratio=9:16`

Ejemplos en `ideas.csv`:

```csv
id,...,render_targets,default_render_target,content_orientation,target_aspect_ratio
101,...,vertical,vertical,portrait,9:16
102,...,horizontal,horizontal,landscape,16:9
103,...,vertical|horizontal,vertical,multi,9:16|16:9
```

## Contrato de render derivado

Los campos resueltos se propagan a:

- `data/index.csv`
- `jobs/<job_id>/job.json`
- `jobs/<job_id>/status.json`
- `jobs/<job_id>/source/<job_id>_visual_manifest.json`
- `jobs/<job_id>/source/<job_id>_scene_prompt_pack.json`
- `jobs/<job_id>/source/<job_id>_scene_prompt_pack.md`

### `index.csv`

El índice derivado ahora incluye:

- `render_targets`
- `default_render_target`
- `content_orientation`

Ejemplo:

```csv
job_id,source_id,estado_csv,idea_central,platform,language,render_targets,default_render_target,content_orientation,brief_created,script_generated,audio_generated,subtitles_generated,visual_manifest_generated,export_ready,last_step,updated_at
000103,103,pending,ejemplo multi target,youtube,es,vertical|horizontal,vertical,multi,True,True,False,False,True,False,visual_manifest_generated,2026-03-28T17:55:46+00:00
```

### `job.json`

Ejemplo vertical:

```json
{
  "render": {
    "targets": ["vertical"],
    "default_target": "vertical",
    "content_orientation": "portrait",
    "aspect_ratios": ["9:16"]
  }
}
```

Ejemplo horizontal:

```json
{
  "render": {
    "targets": ["horizontal"],
    "default_target": "horizontal",
    "content_orientation": "landscape",
    "aspect_ratios": ["16:9"]
  }
}
```

Ejemplo multi target:

```json
{
  "render": {
    "targets": ["vertical", "horizontal"],
    "default_target": "vertical",
    "content_orientation": "multi",
    "aspect_ratios": ["9:16", "16:9"]
  }
}
```

### `status.json`

`status.json` mantiene compatibilidad con el estado actual y añade:

- `render_targets`
- `default_render_target`
- `render_vertical_requested`
- `render_horizontal_requested`
- `render_vertical_ready`
- `render_horizontal_ready`
- `scene_prompt_pack_generated`
- `scene_prompt_pack_file`
- `scene_prompt_pack_markdown_file`

Ejemplo:

```json
{
  "render_targets": ["vertical", "horizontal"],
  "default_render_target": "vertical",
  "render_vertical_requested": true,
  "render_horizontal_requested": true,
  "render_vertical_ready": false,
  "render_horizontal_ready": false,
  "scene_prompt_pack_generated": true,
  "scene_prompt_pack_file": "jobs/000103/source/000103_scene_prompt_pack.json",
  "scene_prompt_pack_markdown_file": "jobs/000103/source/000103_scene_prompt_pack.md"
}
```

### `visual_manifest.json`

El manifest ya no asume `9:16` como contrato universal. Ahora expone:

- `render_targets`
- `default_render_target`
- `content_orientation`
- `target_aspect_ratios`
- `render_profiles`

Ejemplo multi target:

```json
{
  "render_targets": ["vertical", "horizontal"],
  "default_render_target": "vertical",
  "content_orientation": "multi",
  "target_aspect_ratios": ["9:16", "16:9"],
  "render_profiles": {
    "vertical": {
      "aspect_ratio": "9:16",
      "safe_area": "center-weighted mobile frame",
      "platform_behavior": "short-form vertical video, fast clarity, early payoff"
    },
    "horizontal": {
      "aspect_ratio": "16:9",
      "safe_area": "wider composition for desktop and long-form framing",
      "platform_behavior": "landscape framing, stronger lateral composition"
    }
  }
}
```

### `scene_prompt_pack.json`

Nueva capa de salida semántica para producción visual manual en ComfyUI. Se construye de forma determinista usando:

- `brief.json`
- `script.json`
- `visual_manifest.json`
- `visual_manifest.scene_plan`

Cada escena queda alineada con `scene_id`, `scene_role`, `start_sec`, `end_sec` y `text`, y añade:

- `prompt_positive`
- `prompt_negative`
- `action_prompt`
- `continuity_prompt`
- `asset_preference`
- `workflow_profile`
- `copy_paste_block`

Objetivo práctico:

- dejar fichas listas para copiar y pegar en un workflow plantilla fijo de ComfyUI
- evitar una integración técnica temprana con la API de ComfyUI
- preservar continuidad visual y consistencia editorial entre escenas

Ejemplo mínimo:

```json
{
  "job_id": "000001",
  "workflow_target": "comfyui_manual_copy_paste",
  "scenes": [
    {
      "scene_id": "scene_01",
      "scene_role": "hook",
      "asset_preference": "video",
      "workflow_profile": "vertical_hook_qwen",
      "prompt_positive": "hombre 25-45 frustrado pero ambicioso, vertical 9:16 composition, cinematic realism",
      "prompt_negative": "blurry, low quality, bad anatomy, watermark",
      "action_prompt": "subtle head motion, tense breathing, micro-expression shift, slight camera punch-in energy",
      "continuity_prompt": "same core subject: hombre 25-45 frustrado pero ambicioso, same facial identity across all scenes",
      "copy_paste_block": {
        "positive_prompt": "...",
        "negative_prompt": "...",
        "action_prompt": "...",
        "continuity_prompt": "...",
        "workflow_profile": "vertical_hook_qwen",
        "asset_preference": "video",
        "seed": 424242
      }
    }
  ]
}
```

### `scene_prompt_pack.md`

Salida paralela pensada para uso humano rápido. Muestra por escena:

- metadatos temporales
- prompt positivo
- prompt negativo
- action prompt
- continuity prompt
- asset preference
- workflow profile
- bloque listo para copy/paste

## Voz: arquitectura nueva

La identidad vocal ya no se trata como un preset global implícito. Ahora existe un registry persistente y una resolución explícita de estrategia de runtime.

### Qué guarda una voz registrada

Cada voz persistida puede incluir:

- `voice_id`
- `scope`
- `job_id`
- `voice_name`
- `voice_description`
- `model_name`
- `language`
- `seed`
- `voice_instruct`
- `reference_file`
- `reference_text_file`
- `voice_clone_prompt_path`
- `voice_preset`
- `voice_mode`
- `tts_strategy_default`
- `supports_reference_conditioning`
- `supports_clone_prompt`
- `engine`
- `status`
- `notes`
- `created_at`
- `updated_at`

### `voice_id` vs `voice_name`

El sistema separa de forma estricta el identificador técnico del alias humano:

- `voice_id`: identificador persistente generado por el sistema. Ejemplo: `voice_global_0001`.
- `voice_name`: alias lógico legible por humanos. Ejemplo: `marca_personal_es`.

Reglas de integridad:

- `voice_name` debe ser único en todo el registry.
- `voice_name` no puede parecer un ID interno como `voice_global_0001` o `voice_job_000001_0001`.
- si el nombre ya existe, la creación aborta con `ERROR: ya existe una voz con ese nombre`.

### Registry como fuente de verdad

La fuente de verdad del sistema de voces es:

- `video-dataset/voices/voices_index.json`
- `video-dataset/voices/<voice_id>/voice.json`

`job.json` y `status.json` no reemplazan el registry. Lo que hacen es dejar trazabilidad de qué voz se seleccionó y qué estrategia terminó usándose en cada síntesis.

## Semántica de voz y estrategia de runtime

El cambio de diseño importante es este: una voz persistida no se resuelve solo por existir, sino por su tipo operativo.

### Tipos de voz soportados

- `design_only`: voz persistida para VoiceDesign. Debe reutilizar `voice_instruct`, `language`, `seed` y `voice_preset` solo si ese preset está en el propio registro.
- `reference_conditioned`: voz persistida para runtime Base a partir de `reference.wav` y opcionalmente `reference.txt`.
- `clone_prompt`: voz persistida para runtime Base a partir de `voice_clone_prompt_path`.
- `clone_ready`: marcador operativo compatible con ambos casos Base. El runtime deriva si debe usar prompt o referencia según los artefactos realmente disponibles.

### Estrategias derivadas por el runtime

La estrategia efectiva ya no se decide por intuición del wrapper. Se deriva desde el registry:

- `voice_design_from_registry`
- `base_clone_from_reference`
- `base_clone_from_prompt`
- `legacy_preset_fallback`

Regla crítica:

- una voz `design_only` persistida no debe caer en un preset global por defecto
- `QWEN_TTS_VOICE_PRESET` solo debe actuar como fallback legacy cuando no existe una identidad persistida resoluble o cuando una voz legacy fue registrada explícitamente con esa semántica

Limitación importante de `design_only`:

- `design_only` no fija una huella acústica dura entre clips
- en runtime reutiliza `voice_instruct` + `seed` + texto y vuelve a pedirle al modelo que diseñe la voz en cada síntesis
- `reference.wav` queda como trazabilidad y muestra de referencia, pero no se reutiliza como conditioning acústico directo
- por eso puede haber drift de timbre, energía, sexo aparente o edad percibida entre clips aunque la selección de voz sea correcta
- si necesitas máxima consistencia entre clips, la ruta recomendada es convertir la voz a `reference_conditioned` o `clone_prompt` y sintetizar con el runtime Base

Esto evita el fallo operativo más peligroso detectado: que una voz masculina persistida termine sonando femenina porque el runtime acabó aplicando `mujer_podcast_seria_35_45` como preset efectivo.

### Política final de resolución de voz

La selección de voz quedó centralizada. La precedencia es:

1. `--voice-id`
2. `--voice-name`
3. voz ya asignada en `job.json`
4. `VIDEO_DEFAULT_VOICE_ID`
5. fallback legacy solo si no existe una voz persistida resoluble

Ese origen queda trazado como `voice_source` y `voice_selection_mode`.

### Política final de runtime por tipo de voz

Una vez seleccionada la voz, el runtime deriva la estrategia operativa:

- `design_only` -> `voice_design_from_registry` -> runtime `VoiceDesign`
- `clone_prompt` o `clone_ready` con prompt persistido -> `base_clone_from_prompt` -> runtime `Base`
- `reference_conditioned` o `clone_ready` con referencia persistida -> `base_clone_from_reference` -> runtime `Base`
- `legacy_preset_fallback` -> `VoiceDesign` con preset/seed global solo como compatibilidad controlada

Si una voz existe pero su metadata no permite construir una estrategia válida, el sistema falla con error explícito. Ya no debe degradarse silenciosamente a un preset global engañoso.

## Scripts principales del sistema de audio y voces

### `bash wsl/run_design_voice.sh`

Diseña una voz nueva con VoiceDesign, genera `reference.wav`, registra la voz y opcionalmente la asigna a un job.

Salida típica:

- carpeta `video-dataset/voices/<voice_id>/`
- `voice.json`
- `reference.wav`
- `reference.txt`
- actualización de `voices_index.json`

### `bash wsl/run_audio.sh`

Es el flujo batch por jobs. Lee el texto del job, resuelve la voz según la política central y sintetiza con el runtime correcto.

Debe hacer esto:

- si la voz seleccionada es `design_only`, usar VoiceDesign desde el registry
- si la voz seleccionada es `clone_ready`, `clone_prompt` o `reference_conditioned`, usar Base
- si no hay voz persistida, permitir el fallback legacy controlado

Importante sobre el wrapper:

- la línea `Configured fallback preset...` es informativa
- no significa que ese preset se esté usando realmente
- el preset global solo entra en juego si la estrategia efectiva termina siendo `legacy_preset_fallback`
- el runtime ahora imprime siempre la fuente de selección, la voz resuelta y la estrategia efectiva para evitar ambigüedad

### `bash wsl/run_generate_audio_from_prompt.sh`

Es el flujo puntual. Ya no debe entenderse como un flujo exclusivamente clone/reference.

Ahora soporta:

- reutilizar una voz persistida `design_only` por `--voice-id` o `--voice-name`
- reutilizar una voz clone/reference persistida por `--voice-id` o `--voice-name`
- registrar una voz nueva desde `--reference-wav` cuando no existe una voz previa resoluble

### `bash wsl/run_delete_voice.sh`

Ejecuta el borrado consistente de una voz persistida. No debe sustituirse por borrado manual de carpetas.

### `bash wsl/run_reset_audio_state.sh`

Resetea el estado operativo de audio y voces. Es el flujo seguro para limpieza controlada del sistema durante pruebas o reinicios.

Scopes soportados:

- `--scope voices`
- `--scope generated`
- `--scope all`

Seguridad:

- exige `--confirm` para aplicar cambios
- acepta `--dry-run` para inspección sin cambios
- `wsl/reset_system.sh` queda solo como wrapper legacy de compatibilidad

## Trazabilidad de síntesis

El sistema registra al menos estos conceptos:

- `voice_id`
- `voice_name`
- `voice_mode`
- `tts_strategy_requested`
- `tts_strategy_used`
- `tts_fallback_used`
- `tts_fallback_reason`
- `audio_generated_at`

Ejemplo correcto de una voz `design_only` reutilizada sin contaminación de preset global:

```text
[audio] Configured fallback preset (only used if no persistent voice is resolvable): mujer_podcast_seria_35_45
[audio] VIDEO_DEFAULT_VOICE_ID: voice_global_0001
[000001] Voice selection source: global_default
[000001] Voice resolved: voice_global_0001
[000001] Voice name: narrador_documental_es
[000001] Voice mode: design_only
[000001] Requested strategy: description_seed_preset
[000001] Effective runtime strategy: voice_design_from_registry
[000001] Runtime model: voice_design
[000001] Fallback used: false
[000001] Preset source: not_used
[000001] Identity consistency mode: soft_prompt_conditioning_only
[000001] Reference reused in runtime: false
```

Ejemplo correcto de una voz clone/reference:

```text
[000001] Voice selection source: manual_voice_id
[000001] Voice resolved: voice_global_0002
[000001] Voice name: locutor_clone_es
[000001] Voice mode: clone_prompt
[000001] Requested strategy: reference_conditioned
[000001] Effective runtime strategy: clone_prompt
[000001] Runtime model: base
[000001] Fallback used: false
[000001] Identity consistency mode: prompt_anchored_clone
```

Ejemplo de fallback legacy permitido:

```text
[000001] Voice selection source: job_auto_registered
[000001] Voice resolved: voice_job_000001_0001
[000001] Voice name: job_000001_voice
[000001] Voice mode: design_only
[000001] Requested strategy: legacy_preset_fallback
[000001] Effective runtime strategy: legacy_preset_fallback
[000001] Runtime model: voice_design
[000001] Fallback used: false
[000001] Preset used: mujer_podcast_seria_35_45 (source=global_default)
```

## Corrección del alta de voces tras reset

Se corrigió una inconsistencia real en el flujo de creación de voces de `wsl/design_voice.py`.

Qué pasaba:

- el script registraba la voz dos veces
- la primera persistencia escribía `voice.json` y `voices_index.json` antes de terminar de generar y asociar todos los artefactos
- después el mismo flujo volvía a entrar por `register_voice(...)`

Eso hacía que la creación no fuese atómica y abría una ventana de colisión lógica dentro del propio flujo de alta. El filesystem vacío observado después de un reset no contradecía el error histórico, porque la colisión podía producirse durante un intento anterior y luego desaparecer tras la limpieza.

Comportamiento corregido:

- el flujo ahora genera `reference.wav` y `reference.txt` primero
- después hace una única persistencia final en el registry
- `--verbose-voice-debug` permite imprimir rutas efectivas, `voices_index.json`, `voice_id` provisional y búsquedas previas por nombre o por ID

## Borrado y reset del sistema

### Borrado correcto de una voz

No debe borrarse manualmente una carpeta dentro de `video-dataset/voices/`. El flujo correcto es:

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Ese flujo:

- valida que la voz exista
- valida carpeta física y `voice.json`
- bloquea el borrado si la voz sigue referenciada en jobs
- actualiza `voices_index.json`
- hace rollback si algo falla

### Reset total del sistema

Para una limpieza completa y reproducible:

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

Comportamiento:

- `--scope voices`: limpia registry, carpetas de voz y trazas de voz en jobs
- `--scope generated`: limpia audio, subtítulos y logs/metadata derivados de audio
- `--scope all`: aplica ambos
- no borra código, modelos, documentación ni fuentes editoriales base

Este flujo existe para evitar que el estado de pruebas dependa de borrados manuales parciales.

## Ejecución

### Entorno WSL2 para Qwen3-TTS

El entorno operativo válido para audio con Qwen3-TTS en WSL2 es el entorno conda `qwen_gpu`. Ese entorno ya fue verificado con GPU real y es el único que debe considerarse válido como base operativa para los wrappers de audio y de diseño de voz.

Entorno funcional verificado:

- activación: `conda activate qwen_gpu`
- Python válido: `/home/victory/miniconda3/envs/qwen_gpu/bin/python`
- sistema: Windows + WSL2
- distro validada: Ubuntu 24.04 LTS
- GPU validada: NVIDIA GeForce RTX 4070
- Python: `3.12`
- `torch==2.5.1`
- `torchvision==0.20.1`
- `torchaudio==2.5.1`
- CUDA operativa en WSL2
- `qwen_tts` importando correctamente
- `run_design_voice.sh` generando `reference.wav` correctamente

El `venv` antiguo:

```bash
/home/victory/Qwen3-TTS/venv/bin/python
```

ya no debe usarse.

El fallback correcto en los wrappers WSL es:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Esto mantiene dos propiedades importantes:

- si `QWEN_PYTHON` no viene definido, el sistema usa por defecto el Python bueno del entorno `qwen_gpu`
- si `QWEN_PYTHON` ya viene exportado externamente, el wrapper no lo pisa y mantiene compatibilidad con override manual

Comandos de verificación rápida:

```bash
conda activate qwen_gpu
which python
python -V
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Resultado esperado:

- el `python` debe resolver al entorno `qwen_gpu`
- `Python 3.12`
- `torch 2.5.1`
- `True` para CUDA
- `qwen_tts OK`

### Editorial

Desde la raíz:

```bash
python main.py
```

Modo principal actual:

- `python main.py` usa `--source markdown` por defecto y carga historias desde `stories/production/`
- `stories/archive/` queda fuera del flujo editorial normal porque no se escanea por defecto
- cada archivo Markdown debe incluir frontmatter `---` y las secciones `# Titulo`, `## Hook`, `## Historia` y `## CTA`
- el loader normaliza ese Markdown al schema legacy que sigue consumiendo `director.py`
- `data/ideas.csv` se mantiene como formato legacy y sigue soportado con `python main.py --source csv`
- el pipeline imprime `Modelo de texto activo: ...` al arrancar para dejar trazabilidad del modelo efectivo
- cada historia mantiene un `story_id` estable, pero cada ejecución genera un `job_id` nuevo con formato `0004_YYYYMMDD_HHMMSS`
- los outputs nuevos viven en carpetas únicas por ejecución dentro de `video-dataset/jobs/<job_id>/`

Configuración del modelo de texto:

- opción A, fija en código: edita `DEFAULT_TEXT_MODEL` en `config.py`
- opción B, variable de entorno: `TEXT_MODEL=qwen2.5:7b python main.py`
- opción C, override por CLI: `python main.py --text-model qwen2.5:7b`
- precedencia efectiva: `--text-model` > `TEXT_MODEL` > `DEFAULT_TEXT_MODEL`
- helper central: `config.get_text_model()` resuelve el modelo efectivo y es la única fuente de verdad para `director.py`

Verificación rápida:

```bash
python main.py --job-id 000001
```

Debes ver al inicio una línea como:

```text
Modelo de texto activo: qwen3:8b
```

Con override de dataset:

```bash
python main.py --dataset-root /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
```

Solo un job:

```bash
python main.py --job-id 000001
```

Con override puntual de modelo:

```bash
python main.py --job-id 000001 --text-model qwen2.5:7b
```

### Audio VoiceDesign

```bash
bash wsl/run_audio.sh --job-id 000001
```

Con selección manual de voz:

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

Con trazabilidad ampliada:

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite --verbose-voice-debug
```

### Diseñar y registrar voz

Reglas de alta:

- `--voice-name` es un alias logico, no un `voice_id`
- si ya existe ese `voice_name`, el sistema aborta con `ERROR: ya existe una voz con ese nombre`
- si el nombre parece un id interno del sistema, el alta tambien aborta

Voz global:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Prompt recomendado para mayor estabilidad en `design_only`:

```text
Voz masculina nativa en español de España, adulto de 30 a 45 años. Timbre medio-grave, estable y creíble. Dicción clara, ritmo natural, tono profesional y sobrio. Mantener el mismo sexo aparente, edad aparente y timbre entre clips. Evitar exageración expresiva.
```

Qué hace ahora el sistema con `design_only`:

- conserva `voice_description` como trazabilidad
- deriva un `voice_instruct` más corto y orientado a identidad para reducir drift semántico
- sigue sin reutilizar `reference.wav` en runtime mientras la voz siga en `design_only`

Voz de job:

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campaña_a \
  --description "Voz específica de campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

### Audio batch con selección explícita por nombre

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name marca_personal_es \
  --text "Esta es una prueba con una voz persistida de tipo design_only."
```

### Audio puntual clone/reference desde voz existente

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-id voice_global_0002 \
  --text "Esta es una prueba con una voz persistida de tipo clone_ready."
```

### Promocionar una voz `design_only` a `clone_prompt`

```bash
bash wsl/run_promote_voice_to_clone.sh \
  --voice-name marca_personal_es \
  --overwrite \
  --verbose-voice-debug
```

Esto reutiliza `reference.wav` y `reference.txt`, genera `voice_clone_prompt.json` y actualiza la misma voz persistida para que el batch use Base con anclaje acústico fuerte.

### Registrar una voz nueva desde un `reference.wav`

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --register-voice-name locutor_clone_es \
  --reference-wav /mnt/c/ruta/a/reference.wav \
  --reference-text "Texto exacto del reference.wav" \
  --text "Texto final sintetizado con la nueva voz."
  --save-prompt \
  --output /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine/outputs/locutor_clone_es.wav
```

### Subtítulos

```bash
bash wsl/run_subs.sh --job-id 000001
```

### Borrar una voz de forma consistente

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Comportamiento:

- valida que el `voice_id` exista en `voices_index.json`
- valida que existan la carpeta fisica y `voice.json`
- aborta si algun `job.json` sigue referenciando esa voz
- elimina la carpeta de la voz y su entrada en `voices_index.json`
- valida el registry final y hace rollback automatico si algo falla durante el proceso

### Resetear jobs, voces y outputs

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

Inspección sin cambios:

```bash
bash wsl/run_reset_audio_state.sh --scope all --dry-run
```

## Ejemplo concreto de job `000001`

```text
jobs/000001/
├── job.json
├── status.json
├── source/
│   ├── 000001_brief.json
│   ├── 000001_script.json
│   ├── 000001_visual_manifest.json
│   ├── 000001_scene_prompt_pack.json
│   ├── 000001_scene_prompt_pack.md
│   └── 000001_rendered_comfy_workflow.json
├── audio/
│   └── 000001_narration.wav
├── subtitles/
│   └── 000001_narration.srt
└── logs/
    ├── 000001_phase_editorial.log
    ├── 000001_phase_audio.log
    └── 000001_phase_subtitles.log
```

## Ejemplo concreto de voz global

```json
{
  "voice_id": "voice_global_0001",
  "scope": "global",
  "voice_mode": "design_only",
  "job_id": null,
  "voice_name": "marca_personal_es",
  "voice_description": "Voz principal estable para la marca.",
  "model_name": "/mnt/d/.../Qwen3-TTS-12Hz-1.7B-VoiceDesign",
  "language": "Spanish",
  "seed": 424242,
  "voice_instruct": "Voz madura, profesional, sobria y consistente.",
  "reference_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.wav",
  "reference_text_file": "/mnt/c/.../video-dataset/voices/voice_global_0001/reference.txt",
  "tts_strategy_default": "description_seed_preset",
  "supports_reference_conditioning": false,
  "supports_clone_prompt": false,
  "status": "active"
}
```

## Migración desde la estructura anterior

Compatibilidad actual:

- lectura legacy de `jobs/<job_id>/brief.json`
- lectura legacy de `jobs/<job_id>/script.json`
- lectura legacy de `jobs/<job_id>/visual_manifest.json`
- lectura legacy de `jobs/<job_id>/audio/narration.wav`
- lectura legacy de `jobs/<job_id>/subtitles/narration.srt`
- lectura legacy de `jobs/<job_id>/voice.json`

Nuevo comportamiento:

- la escritura nueva usa `source/`, `audio/`, `subtitles/`, `logs/`
- el naming nuevo usa `job_id` en todos los artefactos del job
- la voz ya no queda como texto libre suelto: queda registrada y asignada
- el pipeline editorial ahora deja un `scene_prompt_pack` listo para producción visual manual

Recomendación de migración:

1. definir `VIDEO_DATASET_ROOT`
2. crear la estructura con `bash wsl/create_video_jobs.sh`
3. ejecutar `python main.py`
4. ejecutar audio/subs con los wrappers WSL
5. revisar `job.json`, `status.json` y `voices/voices_index.json`

## Comentarios de diseño

- La resolución de paths vive centralizada en `job_paths.py` y `config.py`.
- `main.py` y `director.py` ya no asumen que `jobs/` del repo es la raíz principal.
- `job.json` es el contrato estable del job.
- `voice_registry.py` separa identidad vocal, asignación a job y persistencia del registry.
- La consistencia vocal ya depende de una identidad persistida, no solo de un preset o texto suelto.

## Troubleshooting resumido

Problemas típicos y causa probable:

- `ERROR: no existe Python ejecutable en ...`
  Suele indicar que `QWEN_PYTHON` apunta al `venv` antiguo o a una ruta inexistente.
- `QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible`
  Suele indicar que no estás en el entorno `qwen_gpu` correcto o que la GPU no está expuesta correctamente dentro de WSL2.
- `ImportError` al importar `torch`, `torchaudio` o `qwen_tts`
  Suele indicar mezcla de entornos, versiones incompatibles o uso accidental del Python antiguo.
- `ERROR: ya existe una voz con ese nombre`
  Indica que `voice_name` ya está registrado y que el alta fue bloqueada para evitar ambigüedad.
- `voice_name no puede parecer un voice_id interno`
  Indica que el alias lógico propuesto se parece a un ID técnico reservado del sistema.
- `ERROR: no se puede eliminar voice_id=... porque sigue referenciada en jobs`
  Indica que la voz aún está asignada o trazada en algún job y el borrado fue bloqueado de forma segura.

Qué hacer:

```bash
conda activate qwen_gpu
which python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Qué no hacer:

- no apuntar manualmente a `/home/victory/Qwen3-TTS/venv/bin/python`
- no borrar carpetas de voces a mano dentro de `video-dataset/voices/`
- no forzar `voice_name` con formato parecido a `voice_global_0001`
- no mezclar entornos de conda y `venv` antiguos

Para troubleshooting detallado y casos históricos:

- consulta `wsl/errores.md`
- consulta `wsl/VOICE_SYSTEM_GUIDE.md`


# VOS SDPA

voice over synthesis con SDPA (sin usar atención tradicional) para evitar problemas de memoria y mejorar la calidad en voces largas.

```bash
export ACCELERATE_USE_SDPA=true
```
