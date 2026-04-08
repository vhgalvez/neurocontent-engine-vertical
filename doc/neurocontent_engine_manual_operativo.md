# NeuroContent Engine — manual operativo completo

**Versión del documento:** 2026-03-29  
**Idioma:** Español  
**Objetivo:** explicar el proyecto de forma fácil, operativa y accionable, con flujo completo, archivos clave, comandos reales y ejemplos de uso listos para copiar.

---

## 1. Qué es este proyecto

`neurocontent-engine` es un **pipeline editorial y de preproducción** para contenido short-form.  
Su función no es renderizar el vídeo final completo, sino preparar todos los artefactos que necesita la fase visual posterior:

- brief normalizado por job
- guion generado con LLM
- `visual_manifest.json` para el pipeline visual aguas abajo
- audio narrado con Qwen3-TTS
- subtítulos `.srt` con WhisperX
- trazabilidad de estado por job
- registro persistente de voces

En otras palabras:

**este repo prepara el contenido**,  
**otro repo/pipeline visual se encarga después de ComfyUI / Wan / edición visual / render final**.

---

## 2. Qué hace exactamente, de principio a fin

### Flujo lógico completo

1. Lees ideas desde `data/ideas.csv`.
2. `main.py` genera o reutiliza:
   - `brief`
   - `script`
   - `visual_manifest`
3. Cada idea se convierte en un **job** con `job_id` de 6 dígitos.
4. El sistema escribe los artefactos dentro de un **dataset externo**.
5. El módulo de voces resuelve si la narración debe salir por:
   - `VoiceDesign`
   - `Base clone/reference`
   - fallback legacy controlado
6. `run_audio.sh` genera el audio narrado.
7. `run_subs.sh` genera subtítulos `.srt` a partir del audio.
8. `status.json`, `job.json`, `voices_index.json` e `index.csv` dejan trazabilidad del proceso.
9. El resultado se consume después desde el pipeline visual.

---

## 3. Lo más importante que debes entender antes de usarlo

### 3.1 Este repo ya no trabaja principalmente sobre `jobs/` dentro del repo

La escritura nueva va a un **dataset externo**, normalmente:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
```

y los jobs viven normalmente en:

```bash
/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs
```

### 3.2 La voz ya no es un simple preset suelto

Ahora existe un **registro persistente de voces** con:

- `voice_id`
- `voice_name`
- `voice_mode`
- `voice.json`
- `voices_index.json`

### 3.3 El repo no es el render final de vídeo

Este proyecto llega hasta:

- guion
- manifest visual
- audio
- subtítulos
- contratos de datos

No hace por sí solo:

- montaje final cinematográfico
- ComfyUI render final
- Wan 2.2 clip final
- export final de vídeo largo/corto

Eso pertenece al pipeline visual posterior.

---

## 4. Estructura conceptual del proyecto

## 4.1 Núcleo editorial

- `main.py`
- `director.py`
- `prompts.py`

Responsables de leer briefs, llamar al LLM, validar el guion y construir el manifest visual.

## 4.2 Resolución de rutas y contratos de archivos

- `config.py`
- `job_paths.py`

Responsables de:

- resolver dataset root
- resolver jobs root
- definir nombres estables de archivos
- mantener compatibilidad con estructura legacy

## 4.3 Sistema de voces

- `voice_registry.py`
- `wsl/design_voice.py`
- `wsl/generate_audio_from_prompt.py`
- `wsl/generar_audio_qwen.py`
- `wsl/delete_voice.py`
- `wsl/reset_audio_state.py`

Responsables de:

- registrar voces
- asignar voces a jobs
- decidir estrategia de runtime
- borrar voces correctamente
- limpiar estado operativo

## 4.4 Wrappers WSL

- `wsl/run_audio.sh`
- `wsl/run_subs.sh`
- `wsl/run_design_voice.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/run_delete_voice.sh`
- `wsl/run_reset_audio_state.sh`
- `wsl/reset_system.sh` (compatibilidad legacy)

Estos wrappers cargan variables de entorno y lanzan los scripts Python reales.

## 4.5 Documentación principal

- `README.md`
- `wsl/VOICE_SYSTEM_GUIDE.md`
- `wsl/AUDIO_GUIDE.md`
- `wsl/errores.md`

---

## 5. Archivos clave y para qué sirve cada uno

| Archivo | Rol real | Cuándo lo usas |
|---|---|---|
| `main.py` | Pipeline editorial principal | Cuando quieres generar briefs, guiones y manifests |
| `config.py` | Configuración global y runtime paths | Siempre, indirectamente |
| `job_paths.py` | Define estructura física de jobs | Siempre, indirectamente |
| `director.py` | Lógica editorial, validación, manifest, index | Cuando ejecutas `python main.py` |
| `prompts.py` | Prompts del LLM para guion y reescritura | Cuando generas guiones |
| `voice_registry.py` | Registro y resolución de voces | Audio y gestión de voces |
| `wsl/generar_audio_qwen.py` | Batch audio por jobs | Audio de los jobs |
| `wsl/generate_audio_from_prompt.py` | Audio puntual o desde voz persistida / referencia | Pruebas rápidas o clonación |
| `wsl/design_voice.py` | Diseñar voz persistida con VoiceDesign | Alta de voces |
| `wsl/generar_subtitulos.py` | Subtítulos por WhisperX | Subtítulos por job |
| `wsl/delete_voice.py` | Borrado consistente de voz | Eliminar voces sin romper registry |
| `wsl/reset_audio_state.py` | Limpieza controlada | Reset de audio / voces / subtítulos |

---

## 6. Estructura real de directorios y artefactos

## 6.1 Dataset raíz

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

## 6.2 Qué significa cada archivo del job

### `job.json`
Contrato estable del job.  
Guarda metadatos estructurados del trabajo:

- `job_id`
- `render`
- `paths`
- `voice`
- `audio_synthesis`
- `artifacts`

### `status.json`
Estado operativo del job.  
Sirve para saber si ya existe:

- brief
- script
- audio
- subtítulos
- manifest
- export ready

También deja huella de voz y estrategia TTS usada.

### `source/<job_id>_brief.json`
Copia persistida del brief leído del CSV.

### `source/<job_id>_script.json`
Guion generado por Ollama y validado por el sistema.

### `source/<job_id>_visual_manifest.json`
Contrato editorial para el pipeline visual downstream.

### `audio/<job_id>_narration.wav`
Narración final del job.

### `subtitles/<job_id>_narration.srt`
Subtítulos generados con WhisperX.

### `logs/`
Logs por fase.

---

## 7. Estructura del CSV de entrada

El archivo base es:

```bash
data/ideas.csv
```

Columnas principales:

```csv
id,estado,nicho,subnicho,idioma,plataforma,formato,duracion_seg,objetivo,avatar,audiencia,dolor_principal,deseo_principal,miedo_principal,angulo,tipo_hook,historia_base,idea_central,tesis,enemigo,error_comun,transformacion_prometida,tono,emocion_principal,emocion_secundaria,nivel_intensidad,cta_tipo,cta_texto,prohibido,keywords,referencias,notas_direccion,ritmo,estilo_narracion,tipo_cierre,nivel_agresividad_copy,objetivo_retencion,render_targets,default_render_target,content_orientation,target_aspect_ratio
```

### Ejemplo real simplificado

```csv
1,pending,finanzas,desarrollo personal,es,tiktok,video_corto,60,atraer,hombre 25-45 frustrado pero ambicioso,personas que trabajan duro sin progreso económico,no llegar a fin de mes,control financiero y libertad,quedarse atrapado en la rutina laboral,verdad_incomoda,afirmacion_directa,"trabajas más que nunca pero sigues igual","trabajar duro no genera riqueza por sí solo","sin estrategia financiera el esfuerzo se diluye","el sistema tiempo-dinero","creer que el sueldo es suficiente","despertar mental hacia ingresos inteligentes",directo,urgencia,ambicion,9,seguir,"Sígueme si quieres salir del sistema","no prometer dinero fácil,no sonar fantasioso","dinero,libertad,ingresos,mentalidad","estilo mentor sobrio","hook en primer segundo + cierre fuerte emocional",rapido,mentor_directo,golpe_emocional,9,alto,vertical,vertical,portrait,9:16
```

---

## 8. `data/index.csv`: el índice derivado

Después de procesar, el sistema escribe:

```bash
data/index.csv
```

Ejemplo real:

```csv
job_id,source_id,estado_csv,idea_central,platform,language,render_targets,default_render_target,content_orientation,brief_created,script_generated,audio_generated,subtitles_generated,visual_manifest_generated,export_ready,last_step,updated_at
000001,1,pending,trabajar duro no genera riqueza por sí solo,tiktok,es,vertical,vertical,portrait,True,True,False,False,True,False,visual_manifest_generated,2026-03-29T01:40:15+00:00
```

Ese archivo sirve para ver rápidamente:

- qué jobs existen
- en qué paso están
- qué falta generar

---

## 9. Resolución de rutas y prioridad

La prioridad real es:

1. argumentos CLI
2. variables de entorno
3. valores por defecto

### Variables principales

```bash
VIDEO_DATASET_ROOT
VIDEO_JOBS_ROOT
VIDEO_DEFAULT_VOICE_ID
QWEN_PYTHON
QWEN_TTS_MODEL_PATH
QWEN_TTS_BASE_MODEL_PATH
QWEN_TTS_DEVICE
QWEN_TTS_VOICE_PRESET
QWEN_TTS_SEED
WHISPERX_PYTHON
```

### Defaults más importantes

```bash
VIDEO_DATASET_ROOT=/mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset
VIDEO_JOBS_ROOT=$VIDEO_DATASET_ROOT/jobs
QWEN_PYTHON=/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

---

## 10. Sistema de voces: explicado fácil

## 10.1 Diferencia entre `voice_id` y `voice_name`

### `voice_id`
Es el identificador técnico persistente del sistema.

Ejemplos:

```text
voice_global_0001
voice_job_000001_0001
```

### `voice_name`
Es el alias humano legible.

Ejemplos:

```text
marca_personal_es
narrador_documental_es
campana_a
```

Regla importante:

- `voice_name` debe ser único
- `voice_name` no puede parecer un `voice_id`

---

## 10.2 Modos de voz

### `design_only`
La voz se reproduce usando **VoiceDesign** a partir de su metadata persistida.

### `reference_conditioned`
La voz se reproduce con el modelo **Base** usando `reference.wav`.

### `clone_prompt`
La voz se reproduce con el modelo **Base** usando `voice_clone_prompt.json`.

### `clone_ready`
Modo híbrido: el runtime decide si usa referencia o prompt, según lo disponible.

---

## 10.3 Estrategias de runtime

La estrategia efectiva puede ser:

- `voice_design_from_registry`
- `base_clone_from_reference`
- `base_clone_from_prompt`
- `legacy_preset_fallback`

Traducción práctica:

- si la voz es `design_only`, usa VoiceDesign
- si la voz es clone/reference, usa Base
- si no hay voz persistida resoluble, puede caer a un preset legacy controlado

---

## 10.4 Orden de selección de voz

La precedencia real es:

1. `--voice-id`
2. `--voice-name`
3. voz ya asignada al `job.json`
4. `VIDEO_DEFAULT_VOICE_ID`
5. fallback legacy

---

## 11. Entorno recomendado real

## 11.1 Audio / voces

El entorno válido documentado es:

```bash
conda activate qwen_gpu
```

Python esperado:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

### Verificaciones rápidas

```bash
conda activate qwen_gpu
which python
python -V
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

## 11.2 Subtítulos

WhisperX usa normalmente:

```bash
WHISPERX_PYTHON=/home/victory/miniconda3/bin/python
```

---

## 12. Flujo rápido recomendado para usar el repo

## 12.1 Paso 1 — ir a la raíz del proyecto

```bash
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine
```

## 12.2 Paso 2 — activar entorno Qwen

```bash
conda activate qwen_gpu
```

## 12.3 Paso 3 — comprobar GPU y librerías

```bash
python -c "import torch; print('cuda', torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

## 12.4 Paso 4 — revisar `data/ideas.csv`

Asegúrate de que cada fila tenga:

- `id`
- `estado=pending`
- `idea_central`
- `cta_texto`
- datos narrativos suficientes

## 12.5 Paso 5 — generar briefs + guiones + manifest

```bash
python main.py
```

## 12.6 Paso 6 — diseñar o seleccionar una voz

Ejemplo voz global:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

## 12.7 Paso 7 — generar audio por job

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

## 12.8 Paso 8 — generar subtítulos

```bash
bash wsl/run_subs.sh --job-id 000001
```

## 12.9 Paso 9 — revisar resultado del job

```bash
tree /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001
```

---

## 13. Comandos principales, con ejemplos reales

## 13.1 Pipeline editorial completo

### Procesar todos los briefs pending

```bash
python main.py
```

### Procesar solo un job

```bash
python main.py --job-id 000001
```

### Procesar varios jobs concretos

```bash
python main.py --job-id 000001 --job-id 000003 --job-id 000010
```

### Cambiar dataset root por CLI

```bash
python main.py \
  --dataset-root /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset \
  --jobs-root /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs
```

---

## 13.2 Diseñar y registrar voz

### Voz global reutilizable

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, sobria, documental, técnica y clara." \
  --reference-text "Bienvenidos. En este análisis vamos a revisar el sistema completo."
```

### Voz asociada a un job

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name campana_a \
  --description "Voz específica de campaña, enérgica pero profesional." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

### Forzar `voice_id`

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-id voice_global_0099 \
  --voice-name voz_demo_controlada \
  --description "Voz neutra controlada." \
  --reference-text "Esta es una referencia controlada."
```

---

## 13.3 Generar audio por jobs

### Un job concreto

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

### Varios jobs concretos

```bash
bash wsl/run_audio.sh --job-id 000001 --job-id 000002 --job-id 000003 --overwrite
```

### Todos los jobs detectados

```bash
bash wsl/run_audio.sh --overwrite
```

### Forzar voz por `voice_id`

```bash
bash wsl/run_audio.sh \
  --job-id 000001 \
  --voice-id voice_global_0001 \
  --overwrite
```

### Forzar voz por `voice_name`

```bash
bash wsl/run_audio.sh \
  --job-id 000001 \
  --voice-name marca_personal_es \
  --overwrite
```

### Probar un clip corto sin jobs

```bash
bash wsl/run_audio.sh \
  --text "Hola, esta es una prueba directa del flujo de audio." \
  --output /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine/outputs/prueba_directa.wav \
  --preset hombre_narrador_sobrio \
  --seed 424242
```

### Usar test corto integrado

```bash
bash wsl/run_audio.sh --test-short
```

### Usar test corto con texto personalizado

```bash
bash wsl/run_audio.sh \
  --test-short \
  --test-text "Probando el sistema batch de Qwen3 TTS con una frase corta."
```

---

## 13.4 Generar audio desde voz persistida o referencia directa

### Reutilizar una voz `design_only` por nombre

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name marca_personal_es \
  --text "Esta es una prueba usando una voz persistida de tipo design_only."
```

### Reutilizar una voz por `voice_id`

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-id voice_global_0001 \
  --text "Esta es otra prueba directa usando el registro de voces."
```

### Reutilizar voz y guardar archivo en ruta explícita

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name narrador_documental_es \
  --text "Bienvenidos. Esta es una prueba usando la voz documental persistida." \
  --output /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine/outputs/narrador_documental_es.wav
```

### Registrar voz nueva desde `reference.wav`

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --register-voice-name locutor_clone_es \
  --reference-wav /mnt/c/ruta/a/reference.wav \
  --reference-text "Texto exacto del reference.wav" \
  --text "Texto final sintetizado con la nueva voz." \
  --save-prompt \
  --output /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine/outputs/locutor_clone_es.wav
```

### Usar JSON de prompt ya serializado

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-clone-prompt /mnt/c/ruta/a/voice_clone_prompt.json \
  --reference-wav /mnt/c/ruta/a/reference.wav \
  --text "Texto sintetizado reutilizando un prompt serializado."
```

### Audio desde job, forzando voz de runtime

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --job-id 000001 \
  --voice-name marca_personal_es \
  --overwrite
```

---

## 13.5 Subtítulos con WhisperX

### Subtítulos para un job

```bash
bash wsl/run_subs.sh --job-id 000001
```

### Subtítulos para varios jobs

```bash
bash wsl/run_subs.sh --job-id 000001 --job-id 000002 --job-id 000003
```

### Subtítulos para todos los jobs

```bash
bash wsl/run_subs.sh
```

### Ejemplo cambiando Python de WhisperX

```bash
export WHISPERX_PYTHON="/home/victory/miniconda3/envs/whisperx/bin/python"
bash wsl/run_subs.sh --job-id 000001
```

---

## 13.6 Gestión de voces

### Borrar una voz correctamente

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

### Lo que NO debes hacer

No borres manualmente:

```bash
rm -rf /mnt/c/.../video-dataset/voices/voice_global_0001
```

Eso puede dejar roto:

- `voices_index.json`
- referencias en jobs
- consistencia del registry

---

## 13.7 Reset y limpieza del sistema

### Importante

`wsl/reset_system.sh` ya es solo un wrapper de compatibilidad.  
El comando operativo real es:

```bash
bash wsl/run_reset_audio_state.sh ...
```

### Ver qué limpiaría, sin ejecutar

```bash
bash wsl/run_reset_audio_state.sh --scope all --dry-run
```

### Limpiar solo audio, subtítulos y logs

```bash
bash wsl/run_reset_audio_state.sh --scope generated --confirm
```

### Limpiar solo voces y referencias de voz

```bash
bash wsl/run_reset_audio_state.sh --scope voices --confirm
```

### Limpiar todo el estado operativo

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

### Wrapper deprecated aún soportado

```bash
bash wsl/reset_system.sh --scope all --confirm
```

---

## 14. Variables de entorno útiles

## 14.1 Ejemplo `wsl/voices.env`

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
export QWEN_TTS_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign"
export QWEN_TTS_VOICE_PRESET="mujer_podcast_seria_35_45"
export QWEN_TTS_SEED="424242"
export QWEN_TTS_LANGUAGE="Spanish"
export QWEN_TTS_DEVICE="auto"
export QWEN_TTS_OVERWRITE="false"
export QWEN_TTS_USE_FLASH_ATTN="false"

export QWEN_TTS_BASE_MODEL_PATH="/mnt/d/AI_Models/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base"
export QWEN_TTS_REFERENCE_TEXT="Hola, esta es una referencia corta para conservar la misma identidad de voz en clips posteriores."
export QWEN_TTS_REFERENCE_LANGUAGE="Spanish"
export QWEN_TTS_REFERENCE_NAME="voz_principal"
export QWEN_TTS_X_VECTOR_ONLY_MODE="false"
```

## 14.2 Seleccionar una voz por defecto global

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
```

Después, si no pasas `--voice-id` ni `--voice-name`, el sistema intentará usar esa voz global.

---

## 15. Qué genera `main.py` exactamente

Cuando ejecutas:

```bash
python main.py
```

el sistema hace esto:

1. lee `data/ideas.csv`
2. valida cabeceras obligatorias
3. filtra filas con `estado=pending`
4. crea o sincroniza `job.json`
5. guarda `brief.json`
6. genera o reutiliza `script.json`
7. genera o reutiliza `visual_manifest.json`
8. actualiza `status.json`
9. reconstruye `data/index.csv`

### Salida típica esperada

```text
Dataset root: /mnt/c/.../video-dataset
Jobs root: /mnt/c/.../video-dataset/jobs
Cargando briefs pendientes...
[1/10] Procesando: trabajar duro no genera riqueza por sí solo
[2/10] Procesando: el error invisible que vacía tu cuenta
...
Pipeline editorial completado.
```

---

## 16. Qué hace `director.py`

`director.py` es el corazón editorial del sistema.

Responsabilidades principales:

- normalizar briefs
- construir el prompt para Ollama
- llamar al modelo
- extraer JSON limpio
- validar el guion
- reescribir `guion_narrado` si la primera respuesta no cumple calidad
- construir `visual_manifest.json`
- sincronizar `status.json`
- construir `data/index.csv`

### Validaciones fuertes del guion

El sistema exige que el JSON tenga estas claves:

- `hook`
- `problema`
- `explicacion`
- `solucion`
- `cierre`
- `cta`
- `guion_narrado`

Además:

- `solucion` debe tener exactamente 3 pasos
- `guion_narrado` debe tener continuidad
- no puede ser una concatenación mecánica
- debe tener al menos 4 frases
- debe tener suficiente longitud para sonar natural en TTS

---

## 17. Qué contiene `visual_manifest.json`

El manifest no es decoración: es el contrato de preproducción visual.

Incluye, entre otros:

- metadata del job
- paths relativos a artefactos
- `render_targets`
- `default_render_target`
- `content_orientation`
- `render_profiles`
- contexto del brief
- contexto del script
- estilo visual
- `character_design`
- `scene_plan`

### Traducción práctica

El manifest sirve para que el pipeline visual downstream sepa:

- qué contar
- cómo dividir escenas
- cómo componer visualmente
- qué audio y subtítulos usar
- qué formato de render se esperaba

---

## 18. Qué hace `voice_registry.py`

Es el módulo más importante del sistema de voces.

Responsabilidades principales:

- cargar y guardar `voices_index.json`
- validar registry
- generar `voice_id`
- asegurar unicidad de `voice_name`
- registrar voces
- asignar voz a un job
- resolver selección de voz
- derivar estrategia de runtime
- localizar referencias activas en jobs
- borrar una voz de forma segura

### Buen resumen mental

`voice_registry.py` es el **sistema operativo de las voces** del proyecto.

---

## 19. Ejemplos completos de uso real

## 19.1 Caso A — producir un job completo desde cero

### 1) generar estructura editorial

```bash
python main.py --job-id 000001
```

### 2) diseñar voz global

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

### 3) generar audio del job usando esa voz

```bash
bash wsl/run_audio.sh \
  --job-id 000001 \
  --voice-name marca_personal_es \
  --overwrite
```

### 4) generar subtítulos

```bash
bash wsl/run_subs.sh --job-id 000001
```

### 5) inspeccionar resultado

```bash
tree /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/video-dataset/jobs/000001
```

---

## 19.2 Caso B — crear voz de campaña solo para un job

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id 000001 \
  --voice-name oferta_semana_1 \
  --description "Voz intensa, directa y convincente para campaña." \
  --reference-text "Esta semana te voy a mostrar algo importante." \
  --assign-to-job
```

Luego:

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

---

## 19.3 Caso C — clonar una voz desde referencia

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --reference-wav /mnt/c/audio/referencia.wav \
  --reference-text "Hola, este es el texto original exacto de la referencia." \
  --register-voice-name locutor_clone_es \
  --text "Ahora esta es la narración final sintetizada con esa misma identidad." \
  --save-prompt \
  --output /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine/outputs/locutor_clone_es.wav
```

---

## 19.4 Caso D — usar una voz global por defecto en todos los jobs

```bash
export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"
bash wsl/run_audio.sh --overwrite
```

Eso hará que, si un job no tiene voz asignada explícitamente, use esa voz global por defecto.

---

## 20. Errores típicos y cómo resolverlos

## 20.1 `ERROR: no existe Python ejecutable en ...`

Causa probable:

- `QWEN_PYTHON` apunta a una ruta vieja
- no estás usando el entorno correcto

Solución:

```bash
conda activate qwen_gpu
which python
echo "$QWEN_PYTHON"
```

Y confirma que apunte a:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

---

## 20.2 `QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible`

Solución:

```bash
conda activate qwen_gpu
python -c "import torch; print(torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"
```

---

## 20.3 `ERROR: ya existe una voz con ese nombre`

La voz ya está registrada.

Haz una de estas dos cosas:

- usa esa voz existente
- crea otra con `voice_name` distinto

---

## 20.4 `voice_name no puede parecer un voice_id interno`

No uses nombres como:

```text
voice_global_0001
voice_job_000001_0001
```

Usa nombres semánticos:

```text
marca_personal_es
locutor_documental_es
campana_black_friday
```

---

## 20.5 `ERROR: no se puede eliminar voice_id=... porque sigue referenciada en jobs`

Significa que la voz todavía aparece en:

- `job.voice.voice_id`
- `job.audio_synthesis.voice_id`

Debes quitar esas referencias o resetear el estado antes de borrarla.

---

## 20.6 WhisperX falla en principal y fallback

Prueba:

```bash
export WHISPERX_PYTHON="/home/victory/miniconda3/envs/whisperx/bin/python"
bash wsl/run_subs.sh --job-id 000001
```

Y revisa los logs del job:

```bash
jobs/000001/logs/
```

---

## 21. Buenas prácticas operativas

- usa siempre `conda activate qwen_gpu` para audio
- no borres voces manualmente
- no edites `voices_index.json` a mano salvo diagnóstico muy controlado
- mantén `voice_name` semánticos y únicos
- usa `--dry-run` antes de un reset destructivo
- trata `job.json` como contrato estable del job
- usa `data/index.csv` como tablero rápido del pipeline
- recuerda que el pipeline visual final está fuera de este repo

---

## 22. Qué comandos usaría yo en el día a día

## Preparar briefs / script / manifest

```bash
python main.py
```

## Producir o actualizar voz principal

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

## Generar audio de 3 jobs concretos

```bash
bash wsl/run_audio.sh \
  --job-id 000001 \
  --job-id 000002 \
  --job-id 000003 \
  --voice-name marca_personal_es \
  --overwrite
```

## Generar subtítulos de esos jobs

```bash
bash wsl/run_subs.sh \
  --job-id 000001 \
  --job-id 000002 \
  --job-id 000003
```

## Limpiar solo audio y subtítulos si vas a regenerar

```bash
bash wsl/run_reset_audio_state.sh --scope generated --confirm
```

---

## 23. Resumen final del flujo real

### Flujo mínimo correcto

```text
ideas.csv
   ↓
python main.py
   ↓
jobs/<job_id>/source/*.json
   ↓
run_design_voice.sh  (opcional si necesitas voz nueva)
   ↓
run_audio.sh
   ↓
audio/<job_id>_narration.wav
   ↓
run_subs.sh
   ↓
subtitles/<job_id>_narration.srt
   ↓
visual pipeline downstream (ComfyUI / Wan / render final)
```

### En una frase

**NeuroContent Engine es el cerebro editorial + audio + subtítulos del sistema, no el render visual final.**

---

## 24. Archivos fuente analizados para este manual

Este manual se construyó analizando directamente estos archivos del repo:

- `README.md`
- `main.py`
- `config.py`
- `job_paths.py`
- `director.py`
- `prompts.py`
- `voice_registry.py`
- `data/ideas.csv`
- `data/index.csv`
- `wsl/VOICE_SYSTEM_GUIDE.md`
- `wsl/AUDIO_GUIDE.md`
- `wsl/errores.md`
- `wsl/voices.env`
- `wsl/run_audio.sh`
- `wsl/run_subs.sh`
- `wsl/run_design_voice.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/run_delete_voice.sh`
- `wsl/run_reset_audio_state.sh`
- `wsl/reset_system.sh`
- `wsl/design_voice.py`
- `wsl/generate_audio_from_prompt.py`
- `wsl/generar_audio_qwen.py`
- `wsl/generar_subtitulos.py`
- `wsl/delete_voice.py`
- `wsl/reset_audio_state.py`

---

## 25. Recomendación práctica final

Si tu objetivo es producir contenido sin complicarte, usa esta secuencia:

```bash
conda activate qwen_gpu
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine
python main.py

bash wsl/run_design_voice.sh --scope global --voice-name marca_personal_es --description "Voz madura, profesional y sobria para la marca." --reference-text "Hola, esta es la voz oficial de la marca."

export VIDEO_DEFAULT_VOICE_ID="voice_global_0001"


bash wsl/run_audio.sh --voice-name marca_personal_es --overwrite

bash wsl/run_audio.sh --job-id 000001 --voice-name marca_personal_es --overwrite
bash wsl/run_subs.sh --job-id 000001
```

Y luego entregas el job resultante al pipeline visual downstream.

---



```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
bash wsl/run_reset_audio_state.sh --scope all --dry-run
bash wsl/run_reset_audio_state.sh --scope all --confirm
bash wsl/run_reset_audio_state.sh --scope voices --confirm
bash wsl/run_reset_audio_state.sh --scope generated --confirm
```