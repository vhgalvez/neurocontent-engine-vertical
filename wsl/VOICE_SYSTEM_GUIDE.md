# Guía Técnica del Sistema de Voces

## 1. Propósito

Este documento es la referencia técnica principal del sistema de voces de `neurocontent-engine`. Explica el diseño operativo actual, las reglas del registry, la resolución de voz, la selección del runtime de síntesis, el borrado consistente y el reset del sistema.

El objetivo no es describir una idea teórica, sino dejar documentado el comportamiento real del proyecto después de las correcciones recientes.

## 2. Resumen ejecutivo

El sistema de voces ya no debe entenderse como una combinación informal de presets y archivos sueltos. Ahora hay cuatro capas diferenciadas:

- registry de voces persistidas
- selección de voz
- derivación de estrategia de runtime
- ejecución de síntesis

La fuente de verdad de identidad vocal es el registry. Los wrappers Bash y los scripts Python no deben inventar una estrategia por su cuenta si ya existe una voz persistida resoluble.

La corrección clave del sistema fue esta:

- una voz persistida `design_only` debe reutilizarse mediante VoiceDesign desde su metadata persistida
- una voz persistida clone/reference debe reutilizarse mediante el runtime Base
- un preset global como `QWEN_TTS_VOICE_PRESET` no debe pisar la identidad de una voz persistida con identidad propia

## 3. Entorno funcional verificado

### 3.1 Plataforma validada

El entorno operativo validado para Qwen3-TTS es:

- Windows con WSL2
- Ubuntu 24.04 LTS
- GPU NVIDIA RTX 4070
- entorno conda `qwen_gpu`

Comando recomendado:

```bash
conda activate qwen_gpu
```

Python válido:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

El `venv` antiguo:

```bash
/home/victory/Qwen3-TTS/venv/bin/python
```

queda documentado solo como referencia histórica y no debe usarse.

### 3.2 Stack funcional verificado

- Python `3.12`
- `torch==2.5.1`
- `torchvision==0.20.1`
- `torchaudio==2.5.1`
- CUDA operativa en WSL2
- `qwen_tts` importando correctamente
- `run_design_voice.sh` generando `reference.wav`

### 3.3 `QWEN_PYTHON` y wrappers WSL

Los wrappers Bash de `wsl/` ejecutan scripts Python reales usando `QWEN_PYTHON`.

Wrappers relevantes:

- `wsl/run_design_voice.sh`
- `wsl/run_audio.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/run_delete_voice.sh`
- `wsl/run_reset_audio_state.sh`

Fallback correcto:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Esto mantiene dos propiedades necesarias:

- el sistema usa por defecto el Python funcional ya validado
- si `QWEN_PYTHON` viene exportado externamente, el wrapper respeta ese override

## 4. Arquitectura del sistema

### 4.1 Capas separadas

El sistema debe entenderse en estas capas:

1. registry: persistencia e integridad de voces
2. selección: cuál es la voz a usar en una operación concreta
3. estrategia: cómo debe sintetizarse esa voz
4. runtime: qué modelo se carga realmente

La capa 1 vive sobre todo en `voice_registry.py`. Las capas 2 y 3 también se centralizan ahí mediante funciones de resolución. La capa 4 se materializa en los scripts de síntesis.

### 4.2 Qué estaba mal antes

El problema histórico no era solo un bug aislado. Había una mezcla de conceptos:

- una voz persistida se trataba a veces como identidad vocal y otras veces como simple referencia para clone
- la selección de voz no estaba unificada entre batch y generación puntual
- el preset global podía contaminar una voz persistida `design_only`

El síntoma operativo más claro era este:

```text
Voice resolved: voice_global_0001 mode=design_only
Requested strategy: description_seed_preset
Preset used: mujer_podcast_seria_35_45 (source=global_default)
```

Eso era incorrecto para una voz persistida con identidad propia.

## 5. Registry de voces

### 5.1 Estructura física

Cada voz vive en:

```text
video-dataset/voices/<voice_id>/
```

Contenido habitual:

- `voice.json`
- `reference.wav`
- `reference.txt`
- opcionalmente `voice_clone_prompt.json`

Índice global:

```text
video-dataset/voices/voices_index.json
```

### 5.2 `voice_id` vs `voice_name`

`voice_id` es el identificador técnico persistente del sistema.

Ejemplos:

- `voice_global_0001`
- `voice_job_000001_0001`

`voice_name` es el alias lógico o semántico de la voz.

Ejemplos:

- `narrador_documental_es`
- `marca_personal_es`
- `campana_q2_es`

Reglas activas:

- `voice_name` debe ser único
- `voice_name` no puede parecer un `voice_id` interno
- el alta aborta si ya existe otra voz con ese nombre

Esto elimina la ambigüedad peligrosa de casos como:

- `voice_id = voice_global_0002`
- `voice_name = voice_global_0001`

### 5.3 Metadata relevante del registry

Campos operativos importantes:

- `voice_mode`
- `tts_strategy_default`
- `voice_instruct`
- `language`
- `seed`
- `voice_preset`
- `reference_file`
- `reference_text_file`
- `voice_clone_prompt_path`
- `supports_reference_conditioning`
- `supports_clone_prompt`

La metadata del registry no es decorativa. Ahora se usa de verdad para decidir el runtime correcto.

## 6. Creación de voces

### 6.1 Flujo de alta con VoiceDesign

El flujo principal de diseño de voz entra por:

```bash
bash wsl/run_design_voice.sh ...
```

Ese wrapper ejecuta `wsl/design_voice.py`.

El flujo:

1. valida el registry antes de operar
2. sintetiza una referencia con VoiceDesign
3. crea `reference.wav`
4. crea `reference.txt`
5. registra la voz en `voice.json`
6. actualiza `voices_index.json`
7. opcionalmente asigna la voz al job

### 6.2 Reglas de creación seguras

Durante el alta:

- `voice_name` no puede estar vacío
- `voice_name` debe ser único
- `voice_name` no puede parecer un ID interno
- si el registry ya está inconsistente, el flujo debe fallar en vez de seguir silenciosamente

### 6.3 Causa corregida de falsa colisión tras reset

Se corrigió un problema real en el flujo histórico de `wsl/design_voice.py`.

El bug no estaba en un caché oculto del registry ni en una segunda fuente de verdad secreta. La causa raíz era que el propio flujo de diseño registraba la voz dos veces:

1. una primera persistencia sin `reference.wav` ni `reference.txt` finales
2. una segunda persistencia para completar la voz

Ese diseño hacía que la creación no fuese atómica. La misma ejecución podía dejar una voz ya escrita en `voices_index.json` y `voice.json` antes de completar el flujo. Después el alta reentraba por `register_voice(...)` otra vez. Aunque el registry pareciese vacío más tarde tras un reset, eso no contradecía el error histórico: el conflicto se había producido en una ejecución anterior del propio alta, no en una fuente externa misteriosa.

La corrección final fue simplificar el flujo:

- validar nombre y `voice_id` provisional antes de sintetizar
- generar los artefactos de referencia
- persistir una sola vez al final

### 6.4 Diagnóstico de alta

Para depurar una alta:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, sobria y documental." \
  --reference-text "Bienvenidos. Esta es una prueba." \
  --verbose-voice-debug
```

Ese modo imprime:

- `runtime.dataset_root`
- `runtime.jobs_root`
- `runtime.voices_root`
- `runtime.voices_index_file`
- `provisional_voice_id`
- `existing_by_name`
- `existing_by_id`
- snapshot del índice cargado

Errores esperados:

```text
ERROR: ya existe una voz con ese nombre
ERROR: voice_name no puede parecer un voice_id interno del sistema
```

### 6.3 Ejemplo

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, sobria, documental, técnica y clara." \
  --reference-text "Bienvenidos. En este análisis vamos a revisar el sistema completo."
```

## 7. Tipos de voz y estrategia de runtime

### 7.1 `voice_mode`

El `voice_mode` describe la naturaleza operativa de la voz persistida.

Modos soportados:

- `design_only`
- `reference_conditioned`
- `clone_prompt`
- `clone_ready`

### 7.2 Qué significa cada modo

#### `design_only`

La voz debe sintetizarse mediante VoiceDesign reutilizando la metadata persistida:

- `voice_instruct`
- `language`
- `seed`
- `voice_preset` solo si está en el propio registro

`reference.wav` puede existir como trazabilidad, pero no debe forzar por sí mismo un flujo clone/reference.

Limitación operativa importante:

- `design_only` no ofrece anclaje acústico fuerte entre clips
- en cada síntesis el modelo vuelve a interpretar `voice_instruct`, `seed` y el texto concreto del guion
- `reference.wav` no se reutiliza como conditioning acústico directo
- por eso puede haber drift perceptivo de timbre, energía, sexo aparente o edad aparente aunque la selección de voz sea correcta
- si necesitas máxima consistencia entre clips, la ruta correcta es `reference_conditioned` o `clone_prompt` con runtime Base

#### `reference_conditioned`

La voz debe sintetizarse mediante el runtime Base reutilizando:

- `reference.wav`
- `reference.txt` o `reference_text_file` cuando exista

#### `clone_prompt`

La voz debe sintetizarse mediante el runtime Base reutilizando:

- `voice_clone_prompt_path`

#### `clone_ready`

Es un modo de compatibilidad que indica que la voz está preparada para runtime Base. La estrategia exacta se deriva según los artefactos disponibles:

- si hay prompt persistido, usa `base_clone_from_prompt`
- si hay referencia reutilizable, usa `base_clone_from_reference`

### 7.3 Estrategias derivadas

La función central que deriva la estrategia operativa es `resolve_voice_runtime_strategy(...)`.

Resultados posibles:

- `voice_design_from_registry`
- `base_clone_from_reference`
- `base_clone_from_prompt`
- `legacy_preset_fallback`

Esta derivación ya no debe repartirse entre wrappers ni quedar implícita en el script que llama.

## 8. Política final de resolución de voz

La función central de selección es `resolve_voice_selection(...)`.

La precedencia final es:

1. `--voice-id`
2. `--voice-name`
3. voz ya asignada en `job.json`
4. `VIDEO_DEFAULT_VOICE_ID`
5. fallback legacy si no existe una voz persistida resoluble

Esta política debe aplicarse igual en:

- `wsl/run_audio.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/generar_audio_qwen.py`
- `wsl/generate_audio_from_prompt.py`

## 9. Uso correcto del preset global

`QWEN_TTS_VOICE_PRESET` sigue existiendo, pero ya no debe entenderse como identidad vocal universal.

Su función correcta es:

- servir de fallback legacy controlado
- permitir compatibilidad con jobs antiguos que todavía no tenían una identidad vocal persistida completa

Su función incorrecta es:

- pisar una voz persistida `design_only`
- alterar una voz clone/reference ya resuelta desde el registry

Regla final:

- si una voz persistida ya tiene identidad propia resoluble, el preset global no debe redefinirla

## 10. Comportamiento por script

### 10.1 `run_audio.sh`

Es el flujo batch por jobs.

Debe:

- resolver la voz por la política central
- derivar la estrategia efectiva desde el registry
- usar VoiceDesign para `design_only`
- usar Base para `clone_ready`, `clone_prompt` o `reference_conditioned`
- dejar trazabilidad en `job.json`, `status.json` y logs
- imprimir siempre la fuente de selección, la voz resuelta, el modo, la estrategia pedida, la estrategia efectiva y si hubo fallback

No debe:

- caer silenciosamente a un preset global si ya existe una voz persistida seleccionada

Importante:

- la línea del wrapper sobre `QWEN_TTS_VOICE_PRESET` es solo configuración de fallback
- no prueba por sí sola que ese preset se esté usando
- el dato fiable es la combinación de:
  - `Voice selection source`
  - `Voice resolved`
  - `Effective runtime strategy`
  - `Preset source`
  - `Fallback used`

### 10.2 `run_generate_audio_from_prompt.sh`

Es el flujo puntual. Ahora debe soportar dos familias de uso:

1. reutilizar una voz persistida existente
2. registrar una voz nueva desde una referencia

Casos válidos:

- `--voice-id` o `--voice-name` para una voz `design_only`
- `--voice-id` o `--voice-name` para una voz clone/reference
- `--reference-wav` para crear una nueva voz reutilizable

### 10.3 `run_design_voice.sh`

Se usa para diseñar y registrar voces nuevas con VoiceDesign. Por defecto genera voces reutilizables de tipo `design_only`.

### 10.4 `run_delete_voice.sh`

Ejecuta el borrado consistente. Debe usarse siempre en lugar de borrar carpetas manualmente.

### 10.5 `run_reset_audio_state.sh`

Ejecuta una limpieza controlada del estado operativo de audio y voces.

## 11. Validación del índice

La validación del registry ahora comprueba:

- `registry_version` soportado
- `voice_id` duplicado
- `voice_name` duplicado
- existencia de carpeta física
- existencia de `voice.json`
- consistencia entre `voice.json` y `voices_index.json`
- validez de `voice_mode`
- validez de `tts_strategy_default`

Esto evita corrupción lógica silenciosa y reduce errores operativos difíciles de rastrear.

## 12. Borrado correcto de voces

### 12.1 Qué no debe hacerse

No debe borrarse manualmente una carpeta dentro de `video-dataset/voices/`.

Eso puede dejar:

- índices inconsistentes
- `voice.json` huérfanos
- referencias colgantes en jobs

### 12.2 Flujo oficial

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

El borrado correcto:

1. valida que la voz exista
2. valida carpeta física y `voice.json`
3. revisa referencias activas en jobs
4. actualiza el índice
5. elimina la carpeta física
6. hace rollback si algo falla

### 12.3 Referencias que bloquean el borrado

El borrado se bloquea si la voz sigue apareciendo en:

- `job.voice.voice_id`
- `job.audio_synthesis.voice_id`

Esto es deliberado. La seguridad del registry tiene prioridad sobre la comodidad de borrar rápido.

## 13. Reset total del sistema

Cuando se necesita un estado limpio de pruebas o desarrollo, el flujo correcto es:

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

Scopes soportados:

- `--scope voices`
- `--scope generated`
- `--scope all`

Seguridad:

- exige `--confirm` para aplicar cambios
- acepta `--dry-run` para inspección sin cambios
- `wsl/reset_system.sh` queda solo como wrapper deprecated de compatibilidad

El reset existe para evitar limpiezas manuales parciales que dejan estados mezclados.

## 14. Troubleshooting específico del sistema de voces

### 14.1 `voice_name` duplicado

```text
ERROR: ya existe una voz con ese nombre
```

Significa que el alias lógico ya existe. Debe reutilizarse la voz existente o elegirse otro nombre.

### 14.2 `voice_name` con forma de ID interno

```text
ERROR: voice_name no puede parecer un voice_id interno del sistema
```

Debe usarse un alias semántico real, no uno con forma de `voice_global_0001`.

### 14.3 Voz persistida no resoluble

Si una voz existe pero su metadata no permite construir una estrategia operativa válida, el runtime debe fallar con un error claro. Ya no debe degradarse silenciosamente a un flujo incorrecto.

### 14.4 Referencias activas al borrar

```text
ERROR: no se puede eliminar voice_id=... porque sigue referenciada en jobs
```

El borrado debe repetirse solo después de corregir esas referencias.

## 15. Comandos operativos reales

### Activar entorno y verificar stack

```bash
conda activate qwen_gpu
which python
python -V
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

### Diseñar una voz persistida

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, documental y sobria." \
  --reference-text "Bienvenidos. Esta es una prueba del sistema."
```

### Reutilizar una voz `design_only`

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name narrador_documental_es \
  --text "Este texto debe sintetizarse con la voz persistida sin aplicar un preset global ajeno."
```

### Reutilizar una voz clone/reference

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-id voice_global_0002 \
  --text "Esta prueba debe usar el runtime Base con la referencia o el prompt persistido."
```

### Batch por job con voz explícita

```bash
bash wsl/run_audio.sh --job-id 000001 --voice-id voice_global_0001 --overwrite
```

### Batch por job con trazabilidad ampliada

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite --verbose-voice-debug
```

### Borrar una voz correctamente

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

### Reset total

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

### Prompt recomendado para `design_only`

Cuando se use `design_only`, conviene priorizar identidad antes que estilo y reducir negaciones. Un prompt más estable suele parecerse a esto:

```text
Voz masculina nativa en español de España, adulto de 30 a 45 años. Timbre medio-grave, estable y creíble. Dicción clara, ritmo natural, tono profesional y sobrio. Mantener el mismo sexo aparente, edad aparente y timbre entre clips. Evitar exageración expresiva.
```

El runtime actual además normaliza `voice_instruct` hacia una versión más corta e identity-first antes de llamar a VoiceDesign. Eso reduce ambigüedad, pero no cambia la limitación principal: mientras la voz siga en `design_only`, `reference.wav` no se reutiliza como conditioning acústico.

### Promocionar una voz `design_only` a `clone_prompt`

Si ya tienes una voz `design_only` con `reference.wav` y quieres máxima estabilidad entre clips, el flujo correcto es:

```bash
bash wsl/run_promote_voice_to_clone.sh \
  --voice-name marca_personal_es \
  --overwrite
```

Ese comando:

- carga el modelo Base
- crea `voice_clone_prompt.json` desde `reference.wav` y `reference.txt`
- actualiza la misma voz persistida a `voice_mode=clone_prompt`
- permite que el batch entre por `base_clone_from_prompt`

## 16. Buenas prácticas

- usar siempre el entorno `qwen_gpu`
- tratar `voice_id` como clave técnica y `voice_name` como alias lógico
- no editar manualmente `voices_index.json`
- no borrar carpetas de voces a mano
- no asumir que `reference.wav` implica siempre clone/reference
- no asumir que una voz persistida debe pasar por el preset global
- revisar `job.json`, `status.json` y logs cuando haya dudas de trazabilidad

## 17. Contexto histórico útil

El sistema conserva cierta compatibilidad con artefactos legacy y con flujos antiguos basados en preset/seed. Esa compatibilidad sigue existiendo para no romper operaciones previas, pero ya no debe confundirse con la arquitectura objetivo.

La arquitectura objetivo es:

- identity first: la voz persistida manda
- strategy explicit: el runtime deriva estrategia desde metadata real
- no silent fallback: si una voz no puede resolverse correctamente, el sistema debe decirlo
