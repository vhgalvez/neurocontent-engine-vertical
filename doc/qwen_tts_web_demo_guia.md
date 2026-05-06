# Qwen TTS Web Demo — Guía técnica para WSL2 + RTX 4070

## Contexto técnico

Qwen TTS se ejecuta mediante el comando:

```bash
qwen-tts-demo Qwen/Qwen3-TTS-12Hz-1.7B-Base --ip 0.0.0.0 --port 8000
```

En tu entorno real, estás usando WSL2 con Conda y el ejecutable está en:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo
```

Los modelos están almacenados en:

```bash
/mnt/d/AI_Models/huggingface/hub/
```

---

## 1. Variables de entorno recomendadas

Antes de lanzar cualquier modelo, exportar estas variables:

```bash
export HF_HOME=/mnt/d/AI_Models/huggingface
export HF_HUB_CACHE=/mnt/d/AI_Models/huggingface/hub
export TRANSFORMERS_CACHE=/mnt/d/AI_Models/huggingface/hub
```

Verificar que están cargadas:

```bash
env | grep -E 'HF_|TRANSFORMERS|HUGGINGFACE'
```

---

## 2. Modelos descargados actualmente

Comando usado para verificar los modelos:

```bash
ls -l /mnt/d/AI_Models/huggingface/hub/
```

Salida actual:

```bash
victory@DESKTOP-1O5BMFF:/$ ls -l /mnt/d/AI_Models/huggingface/hub/
total 0
drwxrwxrwx 1 victory victory 4096 Mar 24 21:38 models--Qwen--Qwen3-TTS-12Hz-0.6B-Base
drwxrwxrwx 1 victory victory 4096 Mar 24 22:23 models--Qwen--Qwen3-TTS-12Hz-1.7B-Base
drwxrwxrwx 1 victory victory 4096 Mar 24 21:36 models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice
drwxrwxrwx 1 victory victory 4096 Mar 24 21:27 models--Qwen--Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

Modelos disponibles:

```text
Qwen/Qwen3-TTS-12Hz-0.6B-Base
Qwen/Qwen3-TTS-12Hz-1.7B-Base
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
```

---

## 3. Para qué sirve cada modelo

| Modelo | Uso recomendado |
|---|---|
| `0.6B-Base` | Pruebas rápidas, timing, audios maqueta |
| `1.7B-Base` | Mejor calidad general y uso con audio de referencia |
| `1.7B-CustomVoice` | Voces/timbres predefinidos |
| `1.7B-VoiceDesign` | Crear una voz nueva desde una descripción |

---

## 4. Modelo ligero para pruebas rápidas

Usar este modelo para generar audios rápidos y medir tiempos:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-0.6B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

Uso recomendado:

```text
Guion → audio rápido → medir duración → ajustar texto → audio final
```

---

## 5. Modelo principal de alta calidad

Usar este modelo para generar audio de mejor calidad o usar audio de referencia:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

Este modelo es el recomendado para:

```text
- Audio final
- Clonación con Reference Audio
- Mantener una voz base creada previamente
```

---

## 6. Clonar o reutilizar una voz personalizada

Para clonar o reutilizar una voz con referencia, usar:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

En la interfaz web:

```text
Reference Audio: audio_base.wav
Reference Text: texto exacto usado en ese audio
Text: nuevo texto a generar
Language: Spanish
```

Regla importante:

```text
Reference Audio + Reference Text deben coincidir.
```

Si el texto de referencia no coincide con el audio, la voz puede cambiar.

---

## 7. Crear voz personalizada con VoiceDesign

Para crear una voz nueva desde una descripción:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

Uso recomendado:

```text
1. Crear una voz con prompt.
2. Generar varias pruebas.
3. Descargar la voz que suene mejor.
4. Guardarla como voz base.
5. Usarla luego en 1.7B-Base como Reference Audio.
```

Ejemplo:

```text
VoiceDesign → mateo_base.wav
1.7B-Base + Reference Audio → voz consistente
```

---

## 8. CustomVoice — voces predefinidas

Para usar voces o timbres predefinidos:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

Uso recomendado:

```text
- Probar voces preset
- Conseguir una voz estable
- Validar rápidamente estilos
```

Limitación:

```text
CustomVoice puede sonar más neutro.
No siempre consigue acento nativo de España/Madrid.
```

---

## 9. Flujo recomendado para crear voces de personajes

Flujo correcto:

```text
1. Usar 1.7B-VoiceDesign para crear una voz.
2. Descargar la mejor voz como archivo .wav.
3. Abrir 1.7B-Base.
4. Usar esa voz como Reference Audio.
5. Usar el texto exacto como Reference Text.
6. Generar todos los audios del personaje con esa misma referencia.
```

Ejemplo:

```text
Mateo:
VoiceDesign → mateo_base.wav
Base + mateo_base.wav → todos los audios de Mateo

Andrés:
VoiceDesign → andres_base.wav
Base + andres_base.wav → todos los audios de Andrés
```

---

## 10. Prompt para voz de Mateo

Mateo tiene 32 años. Es más introspectivo, emocional y pausado.

### Prompt Mateo

```text
gender: Male.
age: 32 years old.
accent: Castilian Spanish from Madrid, Spain.
fluency: Natural and fluent.
clarity: Clear, relaxed pronunciation.
pitch: Medium-low male pitch.
speed: Slow, deliberate pace with natural pauses.
volume: Soft, conversational.
texture: Warm, slightly rough.
emotion: Subtle, controlled, slightly tired.
tone: Introspective and calm.
personality: Reflective, quiet, realistic.
```

### Texto base Mateo

```text
Hola, soy Mateo.

Tengo treinta y dos años.

No todo salió como esperaba.

Pero sigo adelante.

Aunque a veces… no tenga claro hacia dónde voy.
```

Guardar la mejor voz como:

```text
mateo_base.wav
```

---

## 11. Prompt para voz de Andrés

Andrés tiene 30 años. Es compañero de universidad de Mateo. Es más directo, firme y pragmático.

### Prompt Andrés

```text
gender: Male.
age: 30 years old.
accent: Castilian Spanish from Madrid, Spain.
fluency: Natural and fluent.
clarity: High clarity with firm pronunciation.
pitch: Medium male pitch.
speed: Moderate, steady pace.
volume: Clear, projected conversational volume.
texture: Clean and solid.
emotion: Controlled, confident.
tone: Direct and assertive.
personality: Decisive, pragmatic, confident.
```

### Texto base Andrés

```text
Hola, soy Andrés.

Tengo treinta años.

Si algo no funciona…

lo cambias.

No esperas.

Decides.

Y sigues adelante.
```

Guardar la mejor voz como:

```text
andres_base.wav
```

---

## 12. Cómo fijar la voz de Mateo con 1.7B-Base

Primero cerrar VoiceDesign con:

```bash
CTRL + C
```

Luego abrir Base:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

En la interfaz:

```text
Reference Audio: mateo_base.wav

Reference Text:
Hola, soy Mateo.

Tengo treinta y dos años.

No todo salió como esperaba.

Pero sigo adelante.

Aunque a veces… no tenga claro hacia dónde voy.
```

Luego en el texto principal se puede poner cualquier frase nueva de Mateo.

---

## 13. Cómo fijar la voz de Andrés con 1.7B-Base

Abrir Base:

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

En la interfaz:

```text
Reference Audio: andres_base.wav

Reference Text:
Hola, soy Andrés.

Tengo treinta años.

Si algo no funciona…

lo cambias.

No esperas.

Decides.

Y sigues adelante.
```

Luego en el texto principal se puede poner cualquier frase nueva de Andrés.

---

## 14. Prompt para narrador cinematográfico / audiolibro

Formato neutro:

```text
gender: Male.
pitch: Low male pitch, generally stable.
speed: Deliberate pace, slowing slightly after the initial exclamation.
volume: Starts loud, then transitions to a projected conversational volume.
age: Middle-aged adult.
clarity: High clarity with distinct pronunciation.
fluency: Highly fluent.
accent: Castilian Spanish from Madrid, Spain.
texture: Resonant and slightly gravelly.
emotion: Initially commanding, shifting to narrative amusement.
tone: Authoritative start, moving to an engaging, descriptive tone.
personality: Confident and performative.
```

Versión más natural para narración moderna:

```text
gender: Male.
age: 35–45 years old.
accent: Castilian Spanish from Madrid, Spain.
fluency: Natural and fluent.
clarity: High clarity with distinct pronunciation.
pitch: Low male pitch, stable.
speed: Slow, controlled pace with natural pauses.
volume: Projected conversational volume.
texture: Resonant and slightly gravelly.
emotion: Subtle, controlled, cinematic.
tone: Engaging, descriptive and intimate.
personality: Confident, calm and professional.
```

---

## 15. Texto de prueba para narrador

```text
Algunas historias no terminan.

Solo quedan suspendidas.

Como una promesa que nadie se atreve a romper.

Mateo no sabía todavía que aquella llamada iba a cambiarlo todo.

Pero Andrés sí lo sabía.

Y por eso llamó.
```

Guardar la mejor voz como:

```text
narrador_base.wav
```

---

## 16. Reglas para conseguir mejor acento español

Usar instrucciones cortas:

```text
Castilian Spanish from Madrid, Spain.
Native Spanish speaker.
Natural and fluent speech.
Clear pronunciation.
```

Evitar prompts demasiado largos.

Evitar muchas negaciones como:

```text
Do not sound...
Do not...
Do not...
```

Mejor definir en positivo:

```text
Natural conversational speech.
Clear Castilian Spanish pronunciation.
Native Spanish rhythm.
```

---

## 17. Reglas para que Qwen no cambie la voz

VoiceDesign no mantiene la misma voz siempre.

Para mantener la voz:

```text
1. Crear voz con VoiceDesign.
2. Descargar audio.
3. Usar 1.7B-Base.
4. Subir ese audio como Reference Audio.
5. Pegar el Reference Text exacto.
```

Resumen:

```text
VoiceDesign = crear voz
Base = reutilizar / fijar voz
CustomVoice = presets
0.6B = timing rápido
```

---

## 18. Ver duración de un audio

Para medir duración:

```bash
ffprobe -i audio.wav -show_entries format=duration -v quiet -of csv="p=0"
```

Ejemplo:

```bash
ffprobe -i mateo_base.wav -show_entries format=duration -v quiet -of csv="p=0"
```

---

## 19. Regla rápida de tiempos

```text
60 palabras ≈ 30 segundos
120 palabras ≈ 1 minuto
240 palabras ≈ 2 minutos
360 palabras ≈ 3 minutos
```

Para montaje de vídeo IA:

```text
Bloques de 20 a 40 segundos funcionan mejor.
```

---

## 20. Flujo final recomendado para miniserie

```text
1. Escribir guion.
2. Dividir en bloques.
3. Usar Qwen 0.6B para maqueta rápida.
4. Medir tiempos.
5. Crear voces base con VoiceDesign.
6. Fijar voces con 1.7B-Base + Reference Audio.
7. Generar audios finales.
8. Pasar por WhisperX para subtítulos.
9. Montar vídeo con DaVinci / FFmpeg.
```

---

## 21. Comandos rápidos finales

### 0.6B Base — timing rápido

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-0.6B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

### 1.7B VoiceDesign — crear voz

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

### 1.7B Base — clonar/reutilizar voz

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-Base \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

### 1.7B CustomVoice — voces preset

```bash
/home/victory/miniconda3/envs/qwen_gpu/bin/qwen-tts-demo \
Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
--device cuda:0 \
--dtype bfloat16 \
--no-flash-attn \
--ip 0.0.0.0 \
--port 8000
```

---

## 22. Nota sobre errores

Si aparece este warning:

```text
Warning: flash-attn is not installed.
Will only run the manual PyTorch version.
```

No es grave. Solo significa que será más lento.

Si aparece:

```text
Trying to convert audio automatically from float32 to 16-bit int format.
```

No es grave. Gradio está convirtiendo el audio para reproducirlo o descargarlo.

Si aparece:

```text
probability tensor contains either inf, nan or element < 0
```

Probar con:

```bash
--dtype bfloat16
```

en lugar de:

```bash
--dtype float16
```

---

## 23. Decisión práctica

Para producir rápido:

```text
Qwen 0.6B = maqueta rápida
Qwen 1.7B VoiceDesign = crear voz
Qwen 1.7B Base = fijar voz y producir final
Qwen CustomVoice = probar voces preset
```

Para máxima consistencia con referencia:

```text
1.7B-Base + Reference Audio + Reference Text
```
