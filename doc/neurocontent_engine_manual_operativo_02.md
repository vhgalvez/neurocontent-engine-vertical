# Manual Operativo 02

## 1. Qué es este proyecto

`neurocontent-engine-vertical` es un motor de producción de contenido narrativo vertical.

Su función principal es:

1. leer historias Markdown desde un dataset
2. validar que la historia esté bien formada
3. generar un job editorial único por ejecución
4. producir los artefactos base del job
5. dejar el job listo para audio, subtítulos y fases posteriores

El repositorio es el `engine`.
El contenido operativo vive fuera del repo, dentro de un `dataset_root`.

## 2. Idea general del flujo

El flujo recomendado es este:

1. escribes una historia en `stories/draft/`
2. cuando está lista, la mueves a `stories/production/`
3. la marcas con `estado: pending`
4. ejecutas `main.py`
5. el engine crea un `job_id` único
6. genera los archivos editoriales del job
7. si todo sale bien, mueve la historia a `stories/archive/`
8. después ejecutas audio y subtítulos sobre ese `job_id`

Separación conceptual:

- `story_id`: identifica la historia fuente
- `job_id`: identifica una ejecución concreta
- `dataset_root`: separa temáticas o proyectos distintos

## 3. Estructura recomendada del dataset

Cada dataset debe tener esta estructura:

```text
dataset/
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

Significado de cada carpeta:

- `stories/draft/`: historias en preparación. No se procesan.
- `stories/production/`: cola activa de historias listas para procesar.
- `stories/archive/`: historias ya procesadas o archivadas.
- `jobs/`: una carpeta por ejecución.
- `outputs/`: espacio reservado para salidas auxiliares del dataset.
- `logs/`: logs globales del dataset si más adelante se usan.
- `state/`: estado auxiliar del dataset.
- `voices/`: registro persistente de voces del sistema.

## 4. Cómo se resuelve el dataset root

El engine acepta `dataset_root` por este orden:

1. argumento CLI `--dataset-root`
2. variable de entorno `DATASET_ROOT`
3. variable de entorno `VIDEO_DATASET_ROOT`
4. valor por defecto interno del proyecto

En la práctica, la forma más clara es usar siempre `--dataset-root`.

Ejemplo en PowerShell:

```powershell
$DATASET = "C:\video-datasets\historias_oscuras"
python .\main.py --dataset-root $DATASET --dry-run
```

## 4.1 Cómo se define la duración objetivo del audio

El engine permite orientar la longitud de la narración final con una sola variable:

- `TARGET_AUDIO_MINUTES`

Esa variable solo afecta la generación de texto.

Qué significa en la práctica:

- el sistema le indica al modelo de texto cuánto debe durar aproximadamente la narración
- el modelo intenta producir un `guion_narrado` natural y coherente con ese tiempo total
- no necesitas configurar manualmente palabras por minuto
- no necesitas calcular número de palabras
- no necesitas ajustar escenas ni ratios técnicos

Qué no cambia:

- no cambia la lógica del TTS
- no cambia subtítulos
- no cambia prompts de voz
- no cambia clone/reference voice

Formas de usarlo:

1. variable de entorno:

```powershell
$env:TARGET_AUDIO_MINUTES = "2"
python .\main.py --dataset-root $DATASET --story-id 0001
```

2. override puntual por CLI:

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001 --target-audio-minutes 2
```

Si no defines nada:

- el sistema deriva la duración objetivo desde `duracion_seg` del brief

Precedencia práctica:

1. `--target-audio-minutes`
2. `TARGET_AUDIO_MINUTES`
3. derivación automática desde `duracion_seg`

## 5. Historia fuente: formato obligatorio

Las historias operativas son archivos Markdown con front matter YAML.

Ejemplo válido:

```md
---
id: 0001
estado: pending
idioma: es
plataforma: tiktok
formato: video_corto
duracion_seg: 120
objetivo: atraer
render_target: vertical
aspect_ratio: 9:16
tono: storytelling_intimo
ritmo: medio
estilo_narracion: narrativo
tipo_cierre: reflexivo
---

# Título de la historia

## Hook

Aquí va el hook.

## Historia

Aquí va la historia principal.

## CTA

Aquí va el CTA.

## Visual Notes

Notas visuales opcionales.

## Prohibido

Restricciones opcionales.
```

## 6. Reglas obligatorias de una historia

Cada historia debe cumplir esto:

1. estar en `stories/production/` para entrar en cola
2. tener extensión `.md`
3. tener front matter que abra y cierre con `---`
4. tener `id`
5. tener `estado`
6. tener `filename == id`
7. incluir estas secciones:
   - `# Título`
   - `## Hook`
   - `## Historia`
   - `## CTA`

Ejemplo correcto:

- archivo: `stories/production/0001.md`
- front matter: `id: 0001`

Ejemplo incorrecto:

- archivo: `stories/production/0001.md`
- front matter: `id: 0002`

Eso aborta la carga con error claro.

## 7. Estados editoriales soportados

Estados válidos:

- `draft`
- `pending`
- `processing`
- `done`
- `archived`
- `error`

Regla operativa actual:

- el pipeline procesa solo historias con `estado: pending`

Regla de archivado:

- si la ejecución termina bien, la historia se mueve a `stories/archive/` y pasa a `estado: archived`

Si falla:

- la historia no se archiva
- permanece en `stories/production/`
- el job queda marcado como `error`

## 8. story_id y job_id

### 8.1 story_id

`story_id` identifica la historia fuente.

Debe permanecer estable dentro del dataset.

Ejemplo:

- `0001`

### 8.2 job_id

`job_id` identifica una ejecución concreta.

Formato actual:

```text
{story_id}_{YYYYMMDD_HHMMSS}
```

Ejemplo:

```text
0001_20260409_183500
```

Esto permite:

- regenerar una historia sin pisar jobs anteriores
- mantener trazabilidad por ejecución
- separar claramente historia fuente y corrida concreta

## 9. Qué crea el engine al procesar una historia

Cuando procesas una historia, el engine crea una carpeta de job única:

```text
jobs/0001_20260409_183500/
```

Estructura típica:

```text
jobs/
└── 0001_20260409_183500/
    ├── job.json
    ├── status.json
    ├── source/
    │   ├── 0001_20260409_183500_brief.json
    │   ├── 0001_20260409_183500_script.json
    │   ├── 0001_20260409_183500_visual_manifest.json
    │   ├── 0001_20260409_183500_scene_prompt_pack.json
    │   └── 0001_20260409_183500_scene_prompt_pack.md
    ├── audio/
    ├── subtitles/
    └── logs/
```

## 10. Qué guarda `job.json`

`job.json` deja trazabilidad mínima del job.

Campos importantes:

- `job_id`
- `story_id`
- `story_file`
- `story_path`
- `created_at`
- `status`
- `dataset_name`
- `dataset_root`
- `jobs_root`
- `paths.*`

Uso práctico:

- identificar qué historia originó el job
- saber en qué dataset se creó
- resolver rutas sin adivinar nombres

## 11. Qué guarda `status.json`

`status.json` refleja el avance operativo del job.

Campos importantes:

- `brief_created`
- `script_generated`
- `audio_generated`
- `subtitles_generated`
- `visual_manifest_generated`
- `scene_prompt_pack_generated`
- `last_step`
- `updated_at`
- `audio_file`

Uso práctico:

- ver de un vistazo hasta qué fase llegó el job
- saber si audio o subtítulos ya se generaron

## 12. Comando principal del engine

Desde la raíz del repo:

```powershell
python .\main.py --dataset-root C:\video-datasets\historias_oscuras
```

Eso procesa todas las historias `pending` de `stories/production/`.

## 13. Uso recomendado paso a paso

### Paso 1. Entrar al repo

```powershell
cd C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical
```

### Paso 2. Definir el dataset

```powershell
$DATASET = "C:\video-datasets\historias_oscuras"
```

### Paso 3. Crear historia en draft

Ruta:

```text
$DATASET\stories\draft\0001.md
```

### Paso 4. Mover a production

```powershell
Move-Item "$DATASET\stories\draft\0001.md" "$DATASET\stories\production\0001.md"
```

### Paso 5. Validar sin ejecutar

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001 --dry-run
```

Qué valida:

- dataset root
- estructura del dataset
- presencia de la historia en `stories/production/`
- front matter
- `id`
- `estado`
- nombre del archivo
- secciones obligatorias

Si quieres orientar la longitud del texto a un tiempo concreto:

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001 --target-audio-minutes 2 --dry-run
```

### Paso 6. Ejecutar la historia

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001
```

Si quieres forzar una duración objetivo concreta del audio:

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001 --target-audio-minutes 2
```

### Paso 7. Verificar el job creado

```powershell
Get-ChildItem "$DATASET\jobs"
```

Deberías ver algo como:

```text
0001_20260409_183500
```

### Paso 8. Verificar archivado

```powershell
Get-ChildItem "$DATASET\stories\production"
Get-ChildItem "$DATASET\stories\archive"
```

La historia ya no debería estar en `production`.
Debería estar en `archive` con `estado: archived`.

## 14. Procesar una sola historia

La forma recomendada es usar `--story-id`.

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001
```

También existe `--job-id` como alias legacy del filtrado por historia, pero el flujo nuevo recomendado es `--story-id`.

## 15. Procesar todas las historias pendientes

```powershell
python .\main.py --dataset-root $DATASET
```

Esto procesa todas las historias con `estado: pending` dentro de `stories/production/`.

Úsalo solo cuando tengas claro qué historias están listas.

## 16. Qué hace `--dry-run`

`--dry-run` no ejecuta el pipeline completo.

Sirve para:

- validar estructura del dataset
- confirmar que las historias son válidas
- ver qué `story_id` detecta
- ver qué `job_id` se generaría
- ver qué duración objetivo de audio usará la generación de texto
- evitar crear jobs por error

Ejemplo:

```powershell
python .\main.py --dataset-root $DATASET --dry-run
```

## 17. Ejemplo de salida de dry-run

```text
DRY RUN: historias pending detectadas:
- story_id=0001 -> job_id=0001_20260409_183500 -> file=C:/.../stories/production/0001.md
Dry run completado. No se genero ningun job ni se movio ninguna historia.
```

Antes del bloque de dry-run verás una línea como una de estas:

```text
Duracion objetivo de audio: 2.00 minutos
```

o:

```text
Duracion objetivo de audio: derivada desde duracion_seg del brief
```

## 18. Qué pasa si no hay historias pendientes

Mensaje esperado:

```text
No hay historias pending en stories/production para procesar.
```

## 19. Qué pasa si `--story-id` no existe

Mensaje esperado:

```text
No existe la historia solicitada en stories/production: 9999
```

## 20. Qué pasa si el dataset no existe

Mensaje esperado:

```text
No existe el directorio de dataset configurado: ...
```

## 21. Qué pasa si hay ID duplicado

Mensaje esperado:

```text
ID duplicado en historias Markdown dentro del dataset.
- id duplicado: 0001
- archivo actual: ...
- archivo anterior: ...
```

## 22. Qué pasa si filename e id no coinciden

Mensaje esperado:

```text
stories/production/0001.md: el nombre del archivo no coincide con el id interno.
- nombre de archivo: 0001.md
- id en frontmatter: 0002
```

## 23. Qué pasa si el estado es inválido

Mensaje esperado:

```text
estado invalido 'x'. Estados soportados: archived, done, draft, error, pending, processing
```

## 24. Flujo de reejecución de una historia

Si una historia archivada se vuelve a usar:

1. copias o mueves el archivo otra vez a `stories/production/`
2. ajustas el front matter a `estado: pending`
3. vuelves a ejecutar `main.py`

Resultado:

- conserva `story_id`
- crea un `job_id` nuevo
- no pisa el job anterior

## 25. Múltiples datasets por temática

Ejemplos de datasets:

- `C:\video-datasets\historias_oscuras`
- `C:\video-datasets\motivacion`
- `C:\video-datasets\relaciones`

Cada dataset puede empezar en `0001`.

No hay conflicto entre datasets distintos porque:

- el `story_id` solo debe ser único dentro de su dataset
- el `dataset_root` separa completamente las historias, jobs y trazabilidad

## 26. Reset de un dataset

Existe un script auxiliar:

```powershell
python .\reset_dataset.py --dataset-root $DATASET --dry-run
python .\reset_dataset.py --dataset-root $DATASET --yes
```

### Qué limpia

- `stories/draft`
- `stories/production`
- `stories/archive`
- `jobs`
- `outputs`
- `logs`
- `state`

### Qué no toca

- el código del engine
- la carpeta del repo

## 27. Uso de `reset_dataset.py` en PowerShell

### Ver qué borraría

```powershell
$DATASET = "C:\video-datasets\historias_oscuras"
python .\reset_dataset.py --dataset-root $DATASET --dry-run
```

### Ejecutar el reset

```powershell
python .\reset_dataset.py --dataset-root $DATASET --yes
```

### Resultado esperado

- el dataset queda vacío
- la estructura base vuelve a existir
- no se toca el engine

## 28. Audio: cómo se usa después del pipeline editorial

Una vez creado el job, el audio se ejecuta manualmente sobre el `job_id`.

Ejemplo:

```bash
bash wsl/run_audio.sh --job-id 0001_20260409_183500
```

Qué espera el sistema:

- `jobs/<job_id>/source/<job_id>_script.json`

Qué genera:

- `jobs/<job_id>/audio/<job_id>_narration.wav`

## 29. Subtítulos: cómo se usan después del audio

Una vez generado el audio:

```bash
bash wsl/run_subs.sh --job-id 0001_20260409_183500
```

Qué espera el sistema:

- `jobs/<job_id>/audio/<job_id>_narration.wav`

Qué genera:

- `jobs/<job_id>/subtitles/<job_id>_narration.srt`

## 30. Verificación rápida de audio y subtítulos

En PowerShell:

```powershell
Get-ChildItem "$DATASET\jobs\0001_20260409_183500\audio"
Get-ChildItem "$DATASET\jobs\0001_20260409_183500\subtitles"
Get-Content "$DATASET\jobs\0001_20260409_183500\status.json"
```

## 31. Voces: qué hace el sistema

El proyecto soporta registro persistente de voces.

Conceptos importantes:

- `voice_id`: identificador técnico
- `voice_name`: alias humano
- `voice_mode`: modo operativo de la voz
- `tts_strategy_default`: estrategia por defecto

Modos principales:

- `design_only`
- `reference_conditioned`
- `clone_prompt`
- `clone_ready`

Para detalles profundos de voz:

- revisa `wsl/VOICE_SYSTEM_GUIDE.md`
- revisa `wsl/AUDIO_GUIDE.md`

## 32. Comandos principales del proyecto

### Editorial

```powershell
python .\main.py --dataset-root $DATASET --story-id 0001
python .\main.py --dataset-root $DATASET --dry-run
python .\main.py --dataset-root $DATASET
python .\main.py --dataset-root $DATASET --story-id 0001 --target-audio-minutes 2
```

### Reset de dataset

```powershell
python .\reset_dataset.py --dataset-root $DATASET --dry-run
python .\reset_dataset.py --dataset-root $DATASET --yes
```

### Audio

```bash
bash wsl/run_audio.sh --job-id 0001_20260409_183500
```

### Subtítulos

```bash
bash wsl/run_subs.sh --job-id 0001_20260409_183500
```

### Diseño de voz

```bash
bash wsl/run_design_voice.sh --scope global --voice-name marca_personal_es --description "Voz madura y sobria"
```

## 33. Ejemplo de sesión completa en PowerShell

```powershell
cd C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical

$DATASET = "C:\video-datasets\historias_oscuras"

python .\main.py --dataset-root $DATASET --story-id 0001 --dry-run
python .\main.py --dataset-root $DATASET --story-id 0001
python .\main.py --dataset-root $DATASET --story-id 0001 --target-audio-minutes 2

Get-ChildItem "$DATASET\stories\archive"
Get-ChildItem "$DATASET\jobs"
```

Luego, si quieres audio y subtítulos:

```bash
bash wsl/run_audio.sh --job-id 0001_20260409_183500
bash wsl/run_subs.sh --job-id 0001_20260409_183500
```

## 34. Qué revisar si algo falla

### Si no encuentra la historia

Revisa:

- que esté en `stories/production/`
- que el nombre del archivo coincida con el `id`
- que el `story_id` pedido exista

### Si no procesa nada

Revisa:

- que la historia tenga `estado: pending`
- que estés apuntando al dataset correcto
- que no hayas dejado la historia en `draft` o `archive`

### Si falla la validación de Markdown

Revisa:

- front matter abierto y cerrado con `---`
- `id`
- `estado`
- `# Título`
- `## Hook`
- `## Historia`
- `## CTA`

### Si falla audio

Revisa:

- que el job exista
- que el script del job exista
- que `guion_narrado` exista en el JSON
- que el entorno WSL y `qwen_tts` estén correctos

### Si la narración sale demasiado larga o demasiado corta

Revisa:

- si estás usando `--target-audio-minutes`
- si definiste `TARGET_AUDIO_MINUTES`
- si prefieres dejar que el sistema derive la duración desde `duracion_seg`
- que el objetivo sea razonable para el tipo de historia

Regla importante:

- esta configuración afecta solo la generación del texto
- el TTS lee el texto resultante; no corrige por sí mismo una longitud editorial mal planteada

### Si fallan subtítulos

Revisa:

- que el WAV exista en `audio/`
- que WhisperX esté funcionando
- que el `job_id` sea correcto

## 35. Archivos importantes del engine

### `main.py`

Orquestador editorial principal.

Responsabilidades:

- cargar historias
- filtrar por `pending`
- soportar `--story-id`
- soportar `--dry-run`
- crear jobs
- archivar historias tras éxito

### `config.py`

Resuelve:

- dataset root
- jobs root
- modelo de texto
- duración objetivo del audio para generación de texto
- rutas globales derivadas

### `job_paths.py`

Fuente única de rutas del sistema.

Resuelve:

- rutas del dataset
- rutas del job
- nombres de artefactos

### `story_loader.py`

Se encarga de:

- cargar Markdown
- validar metadata
- validar estados
- validar IDs
- archivar historias

### `director.py`

Se encarga de:

- crear el brief normalizado
- generar el script
- generar el visual manifest
- generar el scene prompt pack
- mantener `job.json` y `status.json`

## 36. Recomendación operativa final

El flujo más seguro y simple para producción local es este:

1. escribes en `draft`
2. mueves a `production`
3. usas `--story-id`
4. validas primero con `--dry-run`
5. ejecutas el pipeline
6. verificas que se archive
7. lanzas audio y subtítulos sobre el `job_id`

Ese flujo evita:

- procesar historias por accidente
- mezclar datasets
- pisar jobs anteriores
- perder trazabilidad

## 37. Mejora futura recomendada

Una mejora útil sería añadir `new_story.py` para:

- detectar el siguiente `story_id` libre en el dataset
- crear plantilla Markdown en `stories/draft/`
- reducir errores manuales al crear historias nuevas
