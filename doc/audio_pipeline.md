# Pipeline de Audio y Voces

## Propósito

Este módulo resuelve la identidad vocal y genera narración `.wav` para cada `job`. El audio vive sobre un dataset externo y se opera desde los wrappers de `wsl/`, no llamando directamente a scripts Python salvo diagnóstico puntual.

La lógica principal está en `voice_registry.py`, `voice_prompting.py`, `wsl/design_voice.py`, `wsl/generar_audio_qwen.py`, `wsl/generate_audio_from_prompt.py`, `wsl/promote_voice_to_clone.py`, `wsl/delete_voice.py` y `wsl/reset_audio_state.py`.

## Componentes implicados

- `voice_registry.py`: fuente de verdad del registry de voces y de la política de selección.
- `voice_prompting.py`: preparación de instrucciones de voz.
- `wsl/run_design_voice.sh`: alta de nuevas voces persistidas.
- `wsl/run_audio.sh`: batch de audio por jobs.
- `wsl/run_generate_audio_from_prompt.sh`: pruebas directas o generación puntual.
- `wsl/run_promote_voice_to_clone.sh`: promoción de `design_only` a `clone_prompt`.
- `wsl/run_delete_voice.sh`: borrado consistente.
- `wsl/run_reset_audio_state.sh`: limpieza controlada de voces y audio generado.

## Entorno y wrappers

Los wrappers WSL cargan `wsl/voices.env` y usan `QWEN_PYTHON` para ejecutar los scripts. El entorno documentado por el propio repo es:

```bash
conda activate qwen_gpu
which python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Fallback principal de los wrappers:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Ese fallback es importante porque audio y diseño de voz comparten runtime. Si `QWEN_PYTHON` apunta a otro entorno, el wrapper falla antes de sintetizar.

Cuando la documentación hable de audio operativo, debe asumir siempre el uso de estos wrappers. Invocar directamente los scripts Python tiene sentido solo para diagnóstico o desarrollo muy controlado.

## Registry de voces

La fuente de verdad de las voces es:

```text
<dataset_root>/voices/voices_index.json
<dataset_root>/voices/<voice_id>/voice.json
```

Cada voz tiene:

- `voice_id`: identificador técnico persistente, por ejemplo `voice_global_0001`.
- `voice_name`: alias humano único, por ejemplo `marca_personal_es`.
- `voice_mode`: modo operativo real.
- artefactos opcionales como `reference.wav`, `reference.txt` o `voice_clone_prompt.json`.

`voice_name` debe ser único y no puede parecer un `voice_id`. Esa validación está en `voice_registry.py`, no solo en la documentación.

## Modos de voz y estrategia de runtime

Los modos soportados son:

- `design_only`
- `reference_conditioned`
- `clone_prompt`
- `clone_ready`

La estrategia efectiva se deriva con `resolve_voice_runtime_strategy(...)`:

- `design_only` -> VoiceDesign desde metadata persistida.
- `clone_prompt` -> Base usando `voice_clone_prompt.json`.
- `reference_conditioned` -> Base usando `reference.wav` y, si existe, `reference.txt`.
- `clone_ready` -> Base, resolviendo si usa prompt o referencia según artefactos disponibles.

`QWEN_TTS_VOICE_PRESET` sigue existiendo, pero solo como fallback legacy. No debe interpretarse como identidad principal de una voz persistida.

## Política de selección de voz

La precedencia central está en `voice_registry.py`:

1. `--voice-id`
2. `--voice-name`
3. voz ya asignada en `job.json`
4. `VIDEO_DEFAULT_VOICE_ID`
5. fallback legacy si no existe una voz persistida resoluble

Eso significa que puedes fijar una voz global por entorno, forzar una voz por línea de comandos o dejar que cada job conserve la suya.

## Flujo de audio por módulos

Primero diseñas o registras una voz. Después sintetizas audio batch por `job` o haces pruebas puntuales. Si una voz `design_only` ya funciona pero quieres máxima consistencia entre clips, la promocionas a `clone_prompt`. Cuando ya no la necesitas, la eliminas desde el wrapper oficial.

El módulo de audio escribe normalmente:

```text
jobs/<story_bucket>/<job_id>/audio/<job_id>_narration.wav
```

Y deja trazabilidad en `job.json`, `status.json` y logs del job.

## Comandos reales

### Alta y diseño de voces

Alta de una voz global reutilizable:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Alta de una voz asociada a un job:

```bash
bash wsl/run_design_voice.sh \
  --scope job \
  --job-id h10001_20260409_040719 \
  --voice-name campana_lanzamiento_es \
  --description "Voz concreta para esta campaña." \
  --reference-text "Hola, esta es la voz de esta campaña." \
  --assign-to-job
```

Diseño de voz con trazabilidad ampliada:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, sobria y documental." \
  --reference-text "Bienvenidos. Esta es una prueba." \
  --verbose-voice-debug
```

### Generación de audio por job

Generar audio para un job concreto:

```bash
bash wsl/run_audio.sh --job-id h10001_20260409_040719 --overwrite
```

Forzar voz por `voice-id`:

```bash
bash wsl/run_audio.sh \
  --job-id h10001_20260409_040719 \
  --voice-id voice_global_0001 \
  --overwrite
```

Forzar voz por `voice-name`:

```bash
bash wsl/run_audio.sh \
  --job-id h10001_20260409_040719 \
  --voice-name marca_personal_es \
  --overwrite
```

### Generación puntual y reutilización de voces

Generar audio directo sin job usando una voz registrada por nombre:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name marca_personal_es \
  --text "Esta es una prueba rápida con una voz persistida."
```

Generar audio directo usando una voz registrada por ID:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-id voice_global_0001 \
  --text "Esta es otra prueba rápida de voz."
```

Registrar una voz nueva desde referencia:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --register-voice-name locutor_clone_es \
  --reference-wav /mnt/c/ruta/a/reference.wav \
  --reference-text "Texto exacto del reference.wav" \
  --text "Texto final sintetizado con la nueva voz." \
  --save-prompt \
  --output /mnt/c/ruta/a/outputs/locutor_clone_es.wav
```

### Evolución y mantenimiento del registry

Promocionar una voz `design_only` a `clone_prompt`:

```bash
bash wsl/run_promote_voice_to_clone.sh \
  --voice-name marca_personal_es \
  --overwrite
```

Borrar una voz correctamente:

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Reset del estado de audio y voces:

```bash
bash wsl/run_reset_audio_state.sh --scope generated --dry-run
bash wsl/run_reset_audio_state.sh --scope voices --confirm
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

## Entradas y salidas

Entrada batch:

- `job.json`
- `status.json`
- `source/<job_id>_script.json`
- voz resuelta desde registry o desde flags explícitos

Salida batch:

- `audio/<job_id>_narration.wav`
- `logs/<job_id>_phase_audio.log`
- estado actualizado en `status.json`

Entrada puntual:

- `--text`
- o `--job-id`
- opcionalmente `--voice-id`, `--voice-name` o `--reference-wav`

## Notas importantes

Una voz `design_only` no es una clonación acústica fuerte. Reutiliza identidad semántica e instrucciones, pero cada clip se vuelve a sintetizar desde texto + metadata. Si necesitas máxima estabilidad entre clips, la ruta correcta es `clone_prompt` o `reference_conditioned`.

`run_audio.sh` imprime el preset fallback configurado, pero esa línea no prueba que se haya usado. La señal correcta está en la trazabilidad que imprime el runtime: selección de voz, modo resuelto y estrategia efectiva.

## Troubleshooting básico

Si el wrapper falla con `ERROR: no existe Python ejecutable`, corrige `QWEN_PYTHON`. Si falla diciendo que no existe un `voice_id` o `voice_name`, revisa `voices_index.json` y que estés apuntando al dataset correcto. Si el borrado de una voz se bloquea, normalmente es porque sigue referenciada en `job.voice.voice_id` o en `job.audio_synthesis.voice_id`.

Si dudas entre `voice-id` y `voice-name`, usa `voice-id` como clave técnica y `voice-name` como alias de operación humana. No borres carpetas a mano dentro de `voices/`; eso rompe la consistencia del registry que luego valida `voice_registry.py`.


## Contexto técnico de Qwen TTS web demo

```bash
qwen-tts-demo Qwen/Qwen3-TTS-12Hz-1.7B-Base --ip 0.0.0.0 --port 8000
```

- Comando realista para tu entorno ahora mismo:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype float16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

```bash
victory@DESKTOP-1O5BMFF:/$ ls -l /mnt/d/AI_Models/huggingface/hub/
total 0
drwxrwxrwx 1 victory victory 4096 Mar 24 21:38 models--Qwen--Qwen3-TTS-12Hz-0.6B-Base
drwxrwxrwx 1 victory victory 4096 Mar 24 22:23 models--Qwen--Qwen3-TTS-12Hz-1.7B-Base
drwxrwxrwx 1 victory victory 4096 Mar 24 21:36 models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice
drwxrwxrwx 1 victory victory 4096 Mar 24 21:27 models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign
```