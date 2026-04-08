# Troubleshooting y Estado Verificado de Qwen3-TTS en WSL2

## Propósito de este documento

Este archivo reúne dos cosas distintas que antes estaban mezcladas de forma poco estructurada:

1. el estado verificado del entorno funcional de Qwen3-TTS sobre WSL2
2. una guía operativa de troubleshooting para los problemas más comunes del stack de audio y voces

No sustituye a la guía funcional del sistema de voces. Para eso consulta:

- [VOICE_SYSTEM_GUIDE.md](VOICE_SYSTEM_GUIDE.md)

## A. Entorno funcional verificado

### Sistema operativo y plataforma

El entorno que quedó validado como funcional para Qwen3-TTS es:

- Windows con WSL2
- Ubuntu 24.04 LTS
- kernel `5.15.167.4-microsoft-standard-WSL2`

### Hardware verificado

- GPU: NVIDIA GeForce RTX 4070
- memoria disponible suficiente para el flujo operativo de prueba
- almacenamiento WSL con espacio suficiente

### Entorno Python válido

El entorno que debe usarse es:

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

ya no debe usarse.

### Stack funcional verificado

- Python `3.12`
- `torch==2.5.1`
- `torchvision==0.20.1`
- `torchaudio==2.5.1`
- `pytorch-cuda=12.4`
- `qwen_tts` importando correctamente

### Qué se probó y qué funcionó

Se validaron las siguientes comprobaciones operativas:

- import de PyTorch con CUDA activa
- ejecución real de operaciones tensoriales en GPU
- import correcto de `torchaudio`
- import correcto de `torchvision`
- import correcto de `qwen_tts`
- generación de referencia con `run_design_voice.sh`

Esto es importante porque deja documentado que el problema ya no está en la viabilidad base de Qwen3-TTS sobre WSL2. El foco actual debe ponerse en la operación correcta del registry, los wrappers y la trazabilidad de voces, no en volver a reconstruir el stack desde cero sin necesidad.

Comandos de verificación usados:

```bash
python -c "import torch; print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"
python -c "import torch; x=torch.randn(1024,1024,device='cuda'); y=x@x.T; print('OK GPU', y.shape, y.device)"
python -c "import torchaudio; print('torchaudio', torchaudio.__version__)"
python -c "import torchvision; print('torchvision', torchvision.__version__)"
python -c "import qwen_tts; print('qwen_tts OK')"
```

Salida esperada:

```text
cuda True
gpu NVIDIA GeForce RTX 4070
OK GPU torch.Size([1024, 1024]) cuda:0
torchaudio 2.5.1
torchvision 0.20.1
qwen_tts OK
```

## B. QWEN_PYTHON y wrappers WSL

`QWEN_PYTHON` es la variable que usan los wrappers Bash de `wsl/` para decidir con qué intérprete Python deben ejecutar los scripts de audio, diseño de voz y borrado de voces.

Wrappers relevantes:

- `wsl/run_design_voice.sh`
- `wsl/run_audio.sh`
- `wsl/run_generate_audio_from_prompt.sh`
- `wsl/run_delete_voice.sh`
- `wsl/run_reset_audio_state.sh`

### Por qué antes fallaba

Antes existía un fallback al `venv` antiguo. Cuando ese entorno dejó de existir o dejó de ser el entorno correcto, los wrappers seguían intentando ejecutar Python desde una ruta inválida o desactualizada.

### Valor correcto actual

El fallback correcto es:

```bash
export QWEN_PYTHON="${QWEN_PYTHON:-/home/victory/miniconda3/envs/qwen_gpu/bin/python}"
```

Esto resuelve dos problemas:

- el sistema usa por defecto el Python bueno del entorno validado
- un override externo sigue funcionando porque la sintaxis `${QWEN_PYTHON:-...}` no pisa un valor ya exportado

### Verificación rápida

```bash
conda activate qwen_gpu
which python
python -V
```

## C. Problemas típicos y resolución

### 1. Error por Python inexistente o incorrecto

Síntoma:

```text
ERROR: no existe Python ejecutable en ...
```

Causa probable:

- `QWEN_PYTHON` apunta al `venv` antiguo
- el entorno `qwen_gpu` no está disponible en la ruta esperada
- se ejecutó el wrapper con una variable externa mal exportada

Qué hacer:

```bash
conda activate qwen_gpu
which python
python -V
echo "$QWEN_PYTHON"
```

Qué no hacer:

- no volver a apuntar a `/home/victory/Qwen3-TTS/venv/bin/python`

### 2. CUDA no disponible

Síntoma:

```text
QWEN_TTS_DEVICE=cuda pero CUDA no esta disponible
```

Causa probable:

- no estás en el entorno `qwen_gpu`
- la GPU no está expuesta correctamente dentro de WSL2
- se está usando otro Python distinto del entorno validado

Qué hacer:

```bash
conda activate qwen_gpu
python -c "import torch; print(torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Ninguna')"
```

### 3. Error al importar `torch`

Síntoma histórico observado:

```text
ImportError: ... libtorch_cpu.so: undefined symbol: iJIT_NotifyEvent
```

Ese problema apareció con combinaciones incompatibles del stack MKL/PyTorch. En el entorno validado se resolvió dejando un stack consistente y evitando reinstalaciones aleatorias.

Qué no hacer:

- no mezclar PyTorch CPU con `torchaudio` CUDA
- no mezclar entornos base y `venv` antiguos
- no reinstalar paquetes críticos sin criterio

### 4. `qwen_tts` no importa

Causa probable:

- entorno Python incorrecto
- dependencia no instalada en ese entorno
- el wrapper está ejecutando otro Python

Qué hacer:

```bash
conda activate qwen_gpu
python -c "import qwen_tts; print('qwen_tts OK')"
```

### 5. Error de registry o de integridad de voces

Síntomas posibles:

- `voice_id duplicado en registry`
- `voice_name duplicado en registry`
- falta carpeta física de una voz
- falta `voice.json`
- `voice.json` no coincide con `voices_index.json`

Causa probable:

- edición manual del registry
- borrado manual de carpetas en `video-dataset/voices/`
- alta previa ambigua con documentación vieja o prácticas antiguas

Qué hacer:

- dejar de borrar carpetas manualmente
- usar el flujo oficial de borrado
- usar `bash wsl/run_reset_audio_state.sh --scope all --confirm` si necesitas una limpieza total controlada
- revisar `voice_registry.py`
- revisar `wsl/VOICE_SYSTEM_GUIDE.md`

### 5.b. Error de `voice_name` aparentemente existente tras reset

Síntoma histórico:

```text
ERROR: ya existe una voz con ese nombre (voice_name=..., voice_id=...)
```

incluso después de que un reset posterior dejara `voices_index.json` vacío y `voices/` sin carpetas de voz.

Causa corregida:

- el flujo antiguo de `wsl/design_voice.py` registraba la voz dos veces
- la primera persistencia ocurría antes de terminar los artefactos finales
- la operación no era atómica

Eso significa que el error podía originarse dentro del propio intento de alta y luego desaparecer del filesystem después de un reset. No hacía falta un caché oculto para explicarlo.

Qué hacer ahora:

- usar `--verbose-voice-debug` en `run_design_voice.sh`
- comprobar `runtime.dataset_root`
- comprobar `runtime.voices_root`
- comprobar `provisional_voice_id`
- comprobar `existing_by_name`

### 6. Error por `voice_name` duplicado

Síntoma:

```text
ERROR: ya existe una voz con ese nombre
```

Significado:

Ahora el registry exige unicidad lógica de `voice_name`. Esto evita que existan varias voces distintas con el mismo alias humano.

Qué hacer:

- elegir un `voice_name` nuevo
- o usar directamente el `voice_id` de una voz ya registrada en vez de crear otra

### 7. Error por `voice_name` con forma de ID interno

Síntoma:

```text
ERROR: voice_name no puede parecer un voice_id interno del sistema
```

Significado:

`voice_name` es un alias lógico, no un identificador técnico. Nombres como `voice_global_0001` o `voice_job_000001_0001` son peligrosos porque se confunden con `voice_id`.

### 8. Voz persistida resuelta pero sonido incorrecto por preset global

Síntoma histórico:

```text
Voice resolved: voice_global_0001 mode=design_only
Requested strategy: description_seed_preset
Preset used: mujer_podcast_seria_35_45 (source=global_default)
```

Ese comportamiento era incorrecto cuando la voz ya era una identidad persistida `design_only`. La corrección final del sistema deja esta regla:

- una voz `design_only` persistida debe sintetizarse con VoiceDesign usando su metadata persistida
- `QWEN_TTS_VOICE_PRESET` no debe redefinir esa identidad

Si aun percibes drift aunque la selección sea correcta, la causa más probable ya no es el preset global sino la semántica de `design_only`:

- `design_only` vuelve a interpretar `voice_instruct` en cada clip
- `reference.wav` no se reutiliza como conditioning acústico directo
- textos distintos pueden empujar prosodia y energía de forma distinta
- si el prompt de voz es largo, muy negativo o mezcla demasiadas restricciones, el modelo puede promediar identidad y estilo
- para máxima consistencia entre clips conviene migrar a `reference_conditioned` o `clone_prompt`

Mitigación incorporada:

- el sistema normaliza `voice_instruct` hacia una forma más corta e identity-first antes de usar VoiceDesign
- aun así, esa mitigación no reemplaza el anclaje acústico del flujo Base
- si la voz ya tiene `reference.wav`, conviértela con:

```bash
bash wsl/run_promote_voice_to_clone.sh --voice-name marca_personal_es --overwrite
```

Qué hacer si vuelves a ver un caso parecido:

- revisar que la voz esté bien registrada en `voices_index.json` y `voice.json`
- revisar `voice_mode` y `tts_strategy_default`
- revisar `job.json` y `status.json`
- revisar que el runtime esté entrando por la estrategia derivada desde `voice_registry.py`
- revisar en consola estas líneas:
  - `Voice selection source`
  - `Voice resolved`
  - `Effective runtime strategy`
  - `Preset source`
  - `Fallback used`

### 9. Error al borrar o necesidad de limpieza total

Si el sistema está muy contaminado por pruebas manuales, no conviene seguir borrando carpetas a mano.

Usa:

```bash
bash wsl/run_reset_audio_state.sh --scope all --confirm
```

Eso limpia jobs, voces y el índice global de forma coherente. Si quieres conservar `outputs/`, usa:

```bash
bash wsl/run_reset_audio_state.sh --scope all --dry-run
```

## D. Qué hacer y qué NO hacer

### Haz esto

```bash
conda activate qwen_gpu
which python
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
python -c "import qwen_tts; print('qwen_tts OK')"
```

### No hagas esto

- no usar `/home/victory/Qwen3-TTS/venv/bin/python`
- no borrar carpetas a mano dentro de `video-dataset/voices/`
- no editar `voices_index.json` manualmente salvo diagnóstico excepcional y controlado
- no reutilizar `voice_name` ya existentes
- no crear `voice_name` con formato parecido a `voice_global_0001`

## E. Orden operativo recomendado

```bash
conda activate qwen_gpu
cd /mnt/c/Users/vhgal/Documents/desarrollo/ia/AI-video-automation/neurocontent-engine
python -c "import torch; print(torch.cuda.is_available())"
```

Después:

- diseñar voz con `bash wsl/run_design_voice.sh ...`
- generar audio con `bash wsl/run_audio.sh ...`
- borrar voz solo con `bash wsl/run_delete_voice.sh --voice-id <id>`
- resetear el estado solo con `bash wsl/run_reset_audio_state.sh --scope all --confirm`

## F. Observaciones históricas útiles

Durante la puesta a punto aparecieron warnings que no bloquearon el funcionamiento base:

```text
Warning: flash-attn is not installed. Will only run the manual PyTorch version.
```

y también:

```text
onnxruntime ... Failed to open file: "/sys/class/drm/card0/device/vendor"
```

Ambos mensajes quedaron registrados porque son útiles para troubleshooting futuro, pero no invalidaron el entorno operativo verificado.
