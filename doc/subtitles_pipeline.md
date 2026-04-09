# Pipeline de Subtítulos

## Propósito

Este módulo genera archivos `.srt` a partir del audio de cada job usando WhisperX. No lee el texto editorial como fuente principal: su contrato de entrada es el `.wav` ya sintetizado.

La implementación principal está en `wsl/generar_subtitulos.py` y el wrapper recomendado es `wsl/run_subs.sh`.

## Componentes implicados

- `wsl/run_subs.sh`: wrapper operativo desde WSL.
- `wsl/generar_subtitulos.py`: orquesta preflight, generación principal, fallback y actualización de estado.
- `job_paths.py`: resuelve rutas físicas del audio y del `.srt`.
- `director.py`: expone `update_status(...)`, que subtítulos usa para dejar trazabilidad.

## Contrato entre audio y subtítulos

Subtítulos no debe ejecutarse antes de audio. El script intenta leer primero:

```text
jobs/<story_bucket>/<job_id>/audio/<job_id>_narration.wav
```

Si no existe, prueba una ruta legacy compatible. Si tampoco existe, marca el job como `subs_missing_audio` y no genera nada.

La salida normal es:

```text
jobs/<story_bucket>/<job_id>/subtitles/<job_id>_narration.srt
```

## Flujo paso a paso

1. `run_subs.sh` resuelve `WHISPERX_PYTHON`, `VIDEO_DATASET_ROOT` y `VIDEO_JOBS_ROOT`.
2. `generar_subtitulos.py` hace un preflight con `python -m whisperx --help`.
3. Si pasas `--job-id`, procesa solo esos jobs. Si no, recorre todos los jobs detectados.
4. Para cada job lanza WhisperX sobre el `.wav`.
5. Si la ejecución principal falla, lanza un fallback con `cpu` y `int8`.
6. Renombra o normaliza el `.srt` generado al nombre estable del job.
7. Actualiza `status.json` con `subtitles_generated` y `last_step`.

## Comandos reales

Generar subtítulos para un job:

```bash
bash wsl/run_subs.sh --job-id h10001_20260409_040719
```

Generar subtítulos para varios jobs:

```bash
bash wsl/run_subs.sh --job-id h10001_20260409_040719 --job-id h10002_20260409_051300
```

Procesar todos los jobs detectados:

```bash
bash wsl/run_subs.sh
```

Usar otro Python de WhisperX:

```bash
export WHISPERX_PYTHON="/home/victory/miniconda3/envs/whisperx/bin/python"
bash wsl/run_subs.sh --job-id h10001_20260409_040719
```

## Variables y comportamiento

Variables relevantes:

- `WHISPERX_PYTHON`
- `WHISPERX_MODEL`
- `WHISPERX_LANGUAGE`
- `WHISPERX_DEVICE`
- `WHISPERX_COMPUTE_TYPE`
- `WHISPERX_FALLBACK_DEVICE`
- `WHISPERX_FALLBACK_COMPUTE_TYPE`
- `WHISPERX_OVERWRITE`
- `WHISPERX_STRICT`
- `WHISPERX_PREFLIGHT`

Si `WHISPERX_OVERWRITE=false` y el `.srt` ya existe, el job se marca como `subs_skipped`. Si `WHISPERX_STRICT=true`, el script devuelve error cuando fallan tanto la ejecución principal como el fallback.

## Entradas y salidas

Entrada:

- `audio/<job_id>_narration.wav`
- o una ruta legacy compatible de `narration.wav`

Salida:

- `subtitles/<job_id>_narration.srt`
- `logs/<job_id>_phase_subtitles.log`
- opcionalmente `logs/<job_id>_phase_subtitles_fallback.log`

## Notas importantes

El módulo de subtítulos no intenta regenerar audio ni corregir texto. Si el `.wav` no existe o está mal, el problema está aguas arriba. Su responsabilidad es transcribir el audio disponible y dejar un `.srt` con naming estable dentro del job.

El preflight es útil porque separa problemas de instalación de WhisperX de problemas del contenido concreto del job. Si el preflight falla, corrige primero el entorno.

## Troubleshooting básico

Si `run_subs.sh` falla diciendo que no existe `WHISPERX_PYTHON`, corrige la ruta del intérprete. Si falla el preflight, verifica que `python -m whisperx --help` funcione en ese entorno. Si un job muestra `subs_missing_audio`, ejecuta o regenera antes `wsl/run_audio.sh`.

Si el principal falla pero el fallback funciona, el `.srt` igual puede generarse y el estado del job quedará como `subtitles_generated_fallback`. Si ambos fallan y necesitas que el pipeline no continúe silenciosamente, activa `WHISPERX_STRICT=true`.
