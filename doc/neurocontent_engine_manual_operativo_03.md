Hazlo así, paso a paso
1. Entra en la carpeta correcta
cd C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical
2. Define variables
$PY="C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$DATASET="C:\video-datasets\canal_principal"

Cambia C:\video-datasets\canal_principal por tu dataset real si es otro.

3. Verifica que estás donde toca
Get-Location
Test-Path .\main.py

Debe salir tu ruta del repo y True.

4. Ejecuta en dry-run primero
& $PY .\main.py --dataset-root $DATASET --story-id 0002 --target-audio-minutes 2 --dry-run
5. Si todo va bien, ejecuta normal
& $PY .\main.py --dataset-root $DATASET --story-id 0002 --target-audio-minutes 2
Si quieres ejecutarlo sin cambiar de carpeta

También puedes hacerlo con ruta absoluta:

& "C:\Users\vhgal\AppData\Local\Python\pythoncore-3.14-64\python.exe" `
"C:\Users\vhgal\Documents\desarrollo\ia\AI-video-automation\neurocontent-engine-vertical\main.py" `
--dataset-root "C:\video-datasets\canal_principal" `
--story-id 0002 `
--target-audio-minutes 2 `
--dry-run
Antes de lanzar, revisa esto

Comprueba que exista:

Test-Path "$DATASET\stories\production\0002.md"

Si devuelve False, entonces el problema ya no será el engine sino que no existe esa historia en producción.