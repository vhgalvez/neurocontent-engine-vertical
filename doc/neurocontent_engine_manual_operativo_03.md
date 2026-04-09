Documentación operativa completa
Proyecto: neurocontent-engine-vertical
1. Qué es este proyecto

Este proyecto es un motor de generación de contenido narrativo vertical.

Su función es:

tomar una historia fuente en Markdown
generar un job editorial
generar el texto estructurado del contenido
preparar los artefactos del job
luego generar audio y subtítulos sobre ese job
2. Diferencia entre historia y job
Historia

Es el archivo fuente editorial.

Ejemplo:

stories/production/h10001.md

Ese archivo contiene:

metadatos
hook
historia
CTA
notas visuales

Su identificador es:

id: h10001

Eso es el story_id.

Job

Es una ejecución concreta de esa historia.

Ejemplo:

jobs/h1000/h10001_20260409_040719/

Su identificador es:

h10001_20260409_040719

Eso es el job_id.

Regla importante
Una historia puede tener varios jobs

Porque puedes:

regenerarla
reintentar
sacar otra versión

Ejemplo:

jobs/h1000/h10001_20260409_040719/
jobs/h1000/h10001_20260409_051300/
jobs/h1000/h10001_20260409_090022/

Todo eso sigue siendo la historia h10001.

3. Estructura del dataset

Tu dataset operativo está en algo como:

C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset

Dentro tiene esta estructura:

video-dataset/
├── jobs/
├── logs/
├── outputs/
├── state/
├── stories/
│   ├── draft/
│   ├── production/
│   └── archive/
└── voices/
4. Qué significa cada carpeta
stories/draft/

Historias todavía en preparación.

stories/production/

Historias listas para procesarse.

stories/archive/

Historias ya procesadas o archivadas.

jobs/

Jobs generados por ejecución del pipeline.

logs/

Logs generales del dataset.

outputs/

Salidas o artefactos externos del sistema.

state/

Estado interno del dataset.

voices/

Índice y recursos de voz.

5. Convención de nombres de historia

Tu sistema ahora soporta IDs alfanuméricos como:

h10001
h10002
h20001
Recomendación

Mantén una convención consistente.

Ejemplo:

h10001
h10002
h10003
h20001
Interpretación sugerida
h1000 = familia/bucket
h10001 = historia concreta
6. Estructura correcta de los jobs

Los jobs nuevos quedan así:

jobs/
  h1000/
    h10001_20260409_040719/

No así:

jobs/h1000/h10001/

porque una historia puede tener múltiples ejecuciones.

7. Flujo completo desde cero
Paso 1. Crear una idea

Puedes empezar de dos maneras:

opción A

Escribir directamente una historia Markdown

opción B

Partir de una idea en bruto y luego transformarla en historia

Ejemplo de idea:

un hombre pierde su estatus y descubre que su esposa solo amaba su estilo de vida
Paso 2. Crear la historia fuente

Crea un archivo en:

stories/production/h10001.md

o primero en draft si quieres revisar antes:

stories/draft/h10001.md
Paso 3. Estructura correcta del archivo .md

Ejemplo mínimo:

---
id: h10001
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

# La mujer que amaba la vida, no al hombre

## Hook

Se casó con él cuando tenía dinero, coche, viajes y una vida envidiable.
Pero cuando él lo perdió todo, ella también cambió.

## Historia

Él tenía treinta años y trabajaba como ingeniero de software senior en una startup.
Ganaba bien, hacía consultoría y además tenía un pequeño ecommerce.
Vivían en un apartamento bonito, tenían coche, salían a restaurantes y viajaban con frecuencia.

Ella tenía veintiséis años.
Era atractiva, elegante, carismática y siempre llamaba la atención.
Al principio, lo admiraba y parecía feliz a su lado.

Pero todo cambió cuando él perdió el empleo por la crisis tecnológica y el impacto de la IA.
La consultoría empezó a bajar y el ecommerce cayó casi a la mitad.
Vendieron el coche, dejaron el apartamento y terminaron viviendo en una habitación en un barrio muy pobre.

Fue entonces cuando ella empezó a cambiar.
Salía por las noches, volvía tarde, a veces borracha, distante y fría.
Mientras él intentaba reconstruirse, ella ya estaba buscando fuera la vida que había perdido.

Lo que él no sabía era que ella ya veía a otros hombres mayores, con dinero y con el estilo de vida que él ya no podía darle.

Al final entendió algo doloroso:
ella no amaba al hombre.
Amaba la vida que él representaba.

## CTA

¿Tú crees que algunas personas aman de verdad o solo aman lo que tú puedes ofrecerles?

## Visual Notes

Mostrar primero lujo, estabilidad y vida de pareja ideal.
Después transición a desempleo, pérdida de estatus, habitación pequeña, noches turbias y distancia emocional.

## Prohibido

No sexualizar de forma explícita.
No justificar violencia.
No convertir la historia en odio simplista.
8. Significado del campo estado
draft

historia no lista todavía

pending

lista para procesarse

processing

opcional, en proceso

done

procesada correctamente

archived

archivada

error

falló

9. Regla crítica
Si quieres que se procese, debe tener:
estado: pending

Si tiene:

archived
done
draft
error

el engine no la procesará.

10. Ejecutar el pipeline editorial
Comando base
& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\main.py" `
--dataset-root "C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset" `
--story-id h10001
11. Qué hace ese comando
lee stories/production/h10001.md
valida metadatos y secciones
genera un job_id nuevo
crea el job
genera:
brief
script
visual manifest
scene prompt pack
si todo sale bien:
mueve la historia a stories/archive/h10001.md
cambia estado a archived
12. Qué genera el pipeline

Ejemplo:

jobs/h1000/h10001_20260409_040719/

Dentro:

job.json
status.json
source/
  h10001_20260409_040719_brief.json
  h10001_20260409_040719_script.json
  h10001_20260409_040719_visual_manifest.json
  h10001_20260409_040719_scene_prompt_pack.json
  h10001_20260409_040719_scene_prompt_pack.md
audio/
subtitles/
logs/
13. Qué archivo contiene el texto narrado

El texto que luego se usará para TTS sale del archivo:

jobs/h1000/h10001_20260409_040719/source/h10001_20260409_040719_script.json

Dentro, el campo importante es:

guion_narrado

Ese es el texto que leerá el sistema de audio.

14. Cómo controlar la duración del texto/audio

Tu sistema soporta una duración objetivo.

Por CLI
--target-audio-minutes 2

Ejemplo:

& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\main.py" `
--dataset-root "C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset" `
--story-id h10001 `
--target-audio-minutes 2
Por variable de entorno
$env:TARGET_AUDIO_MINUTES = "2"

Luego:

& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\main.py" `
--dataset-root "C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset" `
--story-id h10001
15. Qué significa esa duración

TARGET_AUDIO_MINUTES no cambia la voz en sí.

Lo que hace es orientar la longitud del texto narrado.

Sí afecta
cantidad de texto generado
extensión esperada del guion_narrado
No afecta directamente
motor TTS
timbre de voz
clonación
subtítulos
16. Qué modelo genera el texto

Tu pipeline editorial está usando:

qwen3:8b

Eso lo viste en la salida:

Modelo de texto activo: qwen3:8b

Ese modelo genera:

hook
problema
explicación
solución
cierre
CTA
guion_narrado
17. Qué modelo genera el audio

El audio lo genera Qwen3-TTS en:

wsl/generar_audio_qwen.py

y lo lanzas normalmente con:

bash wsl/run_audio.sh --job-id h10001_20260409_040719
18. Archivo de audio esperado
jobs/h1000/h10001_20260409_040719/audio/h10001_20260409_040719_narration.wav
19. Cómo generar subtítulos

Cuando ya existe el audio, generas subtítulos con:

bash wsl/run_subs.sh --job-id h10001_20260409_040719
20. Archivo de subtítulos esperado
jobs/h1000/h10001_20260409_040719/subtitles/h10001_20260409_040719_narration.srt
21. Flujo operativo recomendado
Crear historia
stories/production/h10002.md
Asegurar:
estado: pending
Ejecutar pipeline editorial
python main.py --dataset-root ... --story-id h10002
Obtener job
jobs/h1000/h10002_YYYYMMDD_HHMMSS/
Generar audio
bash wsl/run_audio.sh --job-id h10002_YYYYMMDD_HHMMSS
Generar subtítulos
bash wsl/run_subs.sh --job-id h10002_YYYYMMDD_HHMMSS
22. Cómo volver a generar una historia archivada

Si una historia ya está en:

stories/archive/h10001.md

y quieres volver a generar otra ejecución:

Paso 1

Muévela otra vez a producción:

stories/production/h10001.md
Paso 2

Asegura:

estado: pending
Paso 3

Vuelve a ejecutar

Entonces se creará otro job nuevo, por ejemplo:

jobs/h1000/h10001_20260409_090022/
23. Cómo resetear el dataset
Dry run
& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\reset_dataset.py" `
--dataset-root "C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset" `
--dry-run
Reset real
& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\reset_dataset.py" `
--dataset-root "C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\video-dataset" `
--yes
24. Problemas comunes
Problema 1
No hay historias pending en stories/production para procesar.
Causa probable

La historia existe, pero su estado no es pending.

Solución

Revisa el front matter.

Problema 2

La historia no existe en production

Solución

Asegúrate de que el archivo esté realmente en:

stories/production/<story_id>.md
Problema 3

El archivo está en production, pero no entra

Revisa:
id coincide con el nombre
estado: pending
front matter válido
Problema 4

No sabes cuál es el texto final para TTS

Solución

Abre:

jobs/<bucket>/<job_id>/source/<job_id>_script.json

y busca:

guion_narrado
25. Regla final simple
stories/*.md

= historia editorial

jobs/<bucket>/<job_id>/

= ejecución concreta

archive

= historia ya procesada o retirada de la cola

pending

= lista para producir

26. Ejemplo real completo
Historia
stories/production/h10001.md
Job generado
jobs/h1000/h10001_20260409_040719/
Script narrado
jobs/h1000/h10001_20260409_040719/source/h10001_20260409_040719_script.json
Audio
jobs/h1000/h10001_20260409_040719/audio/h10001_20260409_040719_narration.wav
Subtítulos
jobs/h1000/h10001_20260409_040719/subtitles/h10001_20260409_040719_narration.srt
Historia archivada
stories/archive/h10001.md
27. Comandos mínimos que usarás más
Ejecutar historia
python main.py --dataset-root ... --story-id h10001
Ejecutar con duración objetivo
python main.py --dataset-root ... --story-id h10001 --target-audio-minutes 2
Audio
bash wsl/run_audio.sh --job-id h10001_20260409_040719
Subtítulos
bash wsl/run_subs.sh --job-id h10001_20260409_040719
Reset dataset
python reset_dataset.py --dataset-root ... --yes