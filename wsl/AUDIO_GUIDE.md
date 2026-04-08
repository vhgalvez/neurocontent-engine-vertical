# Audio Guide

## Propósito de este documento

Este archivo ya no intenta duplicar toda la documentación del sistema de audio y voces. Su función actual es servir como guía rápida de operación y como índice de navegación hacia la documentación más detallada.

Si necesitas una explicación extensa del sistema de voces, del registry o de la validación de integridad, el documento principal es:

- [VOICE_SYSTEM_GUIDE.md](VOICE_SYSTEM_GUIDE.md)

Si necesitas troubleshooting del entorno Qwen3-TTS en WSL2, el documento principal es:

- [errores.md](errores.md)

Si necesitas la visión general del repositorio y de la estructura de jobs, el documento principal es:

- [README.md](../README.md)

## Estado actual del sistema

El flujo de audio del proyecto opera sobre un dataset externo y no sobre una carpeta `jobs/` interna al repositorio como raíz principal de escritura. La configuración real se resuelve mediante `VIDEO_DATASET_ROOT` y `VIDEO_JOBS_ROOT`.

El sistema de voces ya no debe entenderse como una colección informal de presets. Ahora existe una identidad vocal persistente con trazabilidad explícita:

- `voice_id` técnico persistente
- `voice_name` lógico humano
- `voice.json` por voz
- `voices_index.json` como índice global
- asignación de voz en `job.json`
- rastro operativo en `status.json`

La idea práctica es simple: hoy el audio funciona correctamente cuando se respeta el entorno validado de WSL2, se usan los wrappers oficiales y se trata el registry de voces como una fuente de verdad que no debe manipularse manualmente.

Además, el comportamiento correcto ya distingue tres escenarios operativos:

- una voz persistida `design_only` debe resolverse por VoiceDesign desde el registry
- una voz persistida clone/reference debe resolverse por el runtime Base
- el preset global `QWEN_TTS_VOICE_PRESET` solo debe actuar como fallback legacy y no como identidad de una voz persistida

Limitación importante:

- `design_only` no es una clonación fuerte
- reutiliza `voice_instruct` + `seed` en cada clip
- `reference.wav` queda como trazabilidad y muestra, no como conditioning acústico directo
- el runtime ahora normaliza `voice_instruct` a una versión más identity-first para reducir ambigüedad del prompt
- si buscas máxima estabilidad entre clips, debes migrar a `reference_conditioned` o `clone_prompt`

## Entorno WSL2 verificado

El entorno funcional validado para Qwen3-TTS en WSL2 es:

```bash
conda activate qwen_gpu
```

Python válido:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/python
```

El fallback correcto usado por los wrappers es:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

El entorno antiguo:

```bash
/home/victory/Qwen3-TTS/venv/bin/python
```

debe considerarse obsoleto y no debe volver a usarse.

## Comandos de uso real

Activar entorno y validar Python:

```bash
conda activate qwen_gpu
which python
python -V
```

Validar GPU y stack:

```bash
python -c "import torch; print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"
python -c "import torchaudio; print('torchaudio', torchaudio.__version__)"
python -c "import torchvision; print('torchvision', torchvision.__version__)"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Diseñar una voz nueva:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name marca_personal_es \
  --description "Voz madura, profesional y sobria para la marca." \
  --reference-text "Hola, esta es la voz oficial de la marca."
```

Diseñar una voz nueva con diagnóstico de registry:

```bash
bash wsl/run_design_voice.sh \
  --scope global \
  --voice-name narrador_documental_es \
  --description "Voz masculina adulta, sobria y documental." \
  --reference-text "Bienvenidos. Esta es una prueba." \
  --verbose-voice-debug
```

Generar audio para un job:

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite
```

Generar audio para un job con trazabilidad ampliada:

```bash
bash wsl/run_audio.sh --job-id 000001 --overwrite --verbose-voice-debug
```

Generar audio para una voz persistida `design_only`:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-name marca_personal_es \
  --text "Esta es una prueba usando una voz persistida de tipo design_only."
```

Generar audio clone/reference:

```bash
bash wsl/run_generate_audio_from_prompt.sh \
  --voice-id voice_global_0002 \
  --text "Esta es una prueba usando una voz clone/reference."
```

Promocionar una voz `design_only` existente a `clone_prompt`:

```bash
bash wsl/run_promote_voice_to_clone.sh \
  --voice-name marca_personal_es \
  --overwrite
```

Borrar una voz correctamente:

```bash
bash wsl/run_delete_voice.sh --voice-id voice_global_0001
```

Reset total del sistema:

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

## Reglas operativas importantes

- No borres carpetas manualmente dentro de `video-dataset/voices/`.
- No reutilices `voice_name` ya existentes.
- No uses `voice_name` con forma de `voice_id` interno.
- No asumas que `reference.wav` implica siempre conditioning acústico directo; eso depende de `voice_mode` y de la estrategia real de síntesis.
- No asumas que `QWEN_TTS_VOICE_PRESET` define la identidad de una voz persistida. Ese preset es solo fallback legacy.
- Cuando el wrapper imprime el fallback preset configurado, interprétalo como configuración disponible, no como prueba de uso efectivo.
- No mezcles el entorno conda actual con `venv` antiguos.

## Dónde mirar según el problema

- Error de entorno Python, CUDA, `torch` o `qwen_tts`: [errores.md](errores.md)
- Dudas sobre `voice_id`, `voice_name`, `voices_index.json` o borrado consistente: [VOICE_SYSTEM_GUIDE.md](VOICE_SYSTEM_GUIDE.md)
- Dudas sobre estructura de jobs, dataset o pipeline editorial: [README.md](../README.md)
