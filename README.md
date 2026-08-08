# Win64 Template Builder

**Win64 Template Builder** es una herramienta CLI multiplataforma (Linux / Windows / Wine) diseñada para generar copias personalizadas de estructuras de carpetas a partir de una plantilla inmutable `Win64.rar`.

La herramienta cuenta con una interfaz interactiva con animaciones de consola, spinners dinámicos, formateo con colores ANSI y validaciones estrictas para garantizar la compatibilidad entre Linux y Windows.

---

## 📋 Requisitos del Sistema

### 1. Entorno de Ejecución Python
* **Python >= 3.11** (Librería estándar únicamente, sin dependencias de producción externas).

### 2. Extractor de Archivos RAR
Para extraer la plantilla base `Win64.rar`, el sistema debe contar con **uno** de los siguientes comandos en su `$PATH`:
* `7z` / `7zz` (Recomendado)
* `unrar`

#### Instalación del extractor RAR por distribución Linux:

* **Arch Linux / CachyOS / Manjaro**:
  ```bash
  sudo pacman -S 7zip
  ```
* **Ubuntu / Debian**:
  ```bash
  sudo apt install 7zip
  # o alternativamente: sudo apt install unrar
  ```
* **Fedora**:
  ```bash
  sudo dnf install p7zip p7zip-plugins
  ```

---

## 🍷 Requisitos y Configuración de Wine (Linux desde cero)

Al ejecutar aplicaciones `.exe` generadas en un sistema Linux limpio a través de **Wine**, es común que Wine solicite o requiera instalar dependencias adicionales al ejecutarse por primera vez.

### ¿Por qué sucede esto?
Un prefijo de Wine limpio (`~/.wine`) carece de librerías nativas de Windows, fuentes del sistema y componentes de tiempo de ejecución de DirectX/VCRuntime.

### Dependencias recomendadas para Wine desde cero:

1. **Paquetes base del sistema (Arch / CachyOS)**:
   ```bash
   sudo pacman -S wine winetricks wine-gecko wine-mono vulkan-icd-loader lib32-vulkan-icd-loader lib32-gnutls
   ```

2. **Paquetes base del sistema (Ubuntu / Debian)**:
   ```bash
   sudo apt install wine winetricks wine-gecko wine-mono
   ```

3. **Inicialización y librerías comunes mediante `winetricks`**:
   Para evitar que Wine pida dependencias continuamente al abrir ejecutables, se sugiere preparar el prefijo básico:
   ```bash
   # Inicializar prefijo de 64 bits
   WINEPREFIX=~/.wine WINEARCH=win64 wineboot -u

   # (Opcional) Instalación de runtime común y fuentes
   winetricks corefonts vcrun2015 d3dcompiler_47
   ```

---

## 🚀 Guía de Uso

### 1. Modo Interactivo Animado (Predeterminado)
Ejecute el programa en la consola para iniciar el asistente gráfico e interactivo:

```bash
python3 main.py
```

El asistente le solicitará paso a paso:
1. **Nombre de la carpeta principal** (ej. `Shift At Midnight Demo`).
2. **Nombre del ejecutable** (ej. `Shift At Midnight.exe`). Si omite la extensión `.exe`, se agregará automáticamente.
3. **Tipo de estructura / layout**:
   - `[1] Carpeta directa`: `Output/Carpeta/`
   - `[2] Estructura Steam`: `Output/steamapps/common/Juego/`
   - `[3] Ruta personalizada`: Ruta relativa definida por el usuario.
4. **Directorio de salida**.

---

### 2. Inspección de la Plantilla (`inspect`)
Permite verificar la inmutabilidad, el hash SHA-256, los ejecutables candidatos y la estructura interna del archivo `Win64.rar` sin modificar ni extraer nada:

```bash
python3 main.py inspect
```

Ejemplo de salida:
```text
╭────────────────────────────────────────────────────────╮
│ Plantilla: /ruta/a/Win64.rar                          │
╰────────────────────────────────────────────────────────╯

Root:
  Win64/

Directorios / Idiomas:
  ├── es-MX/

Archivos detectados:
  ├── WordpadFilter.dll
  ├── Rouge-Win64-Shipping.exe
  ├── es-MX/wordpad.exe.mui
  ├── en-US
  ├── es-MX

Candidatos a ejecutable raíz:
  ➜ Rouge-Win64-Shipping.exe

Estado:
  ✓ Plantilla válida e inmutable
```

---

### 3. Modo Simulación (`--dry-run`)
Muestra la vista previa del árbol de directorios que se crearía sin tocar el sistema de archivos:

```bash
python3 main.py --folder "My Game" --exe "MyGame.exe" --layout direct --dry-run
```

---

### 4. Automatización CLI (Modo No Interactivo)
Puede automatizar la generación especificando todos los parámetros en la línea de comandos:

#### Layout Directo:
```bash
python3 main.py \
  --folder "Shift At Midnight Demo" \
  --exe "Shift At Midnight.exe" \
  --layout direct \
  --output "~/Descargas/win64"
```

#### Layout Estructura Steam:
```bash
python3 main.py \
  --folder "Example Game" \
  --exe "ExampleGame.exe" \
  --layout steam \
  --output "./output"
```

#### Layout Steam apuntando a una biblioteca real (`--steam-library`):
```bash
python3 main.py \
  --folder "Example Game" \
  --exe "ExampleGame.exe" \
  --layout steam \
  --steam-library "/mnt/games/SteamLibrary"
```

#### Layout Personalizado:
```bash
python3 main.py \
  --folder "Custom Game" \
  --exe "Game.exe" \
  --layout custom \
  --custom-path "steamapps/common/MyGame/Binaries/Win64"
```

---

### 5. Limpieza de Artefactos Temporales (`clean`)
Elimina exclusivamente archivos temporales etiquetados con el prefijo `.win64-builder-*`:

```bash
python3 main.py clean
```

---

## 🧪 Ejecución de Pruebas Automatizadas

El proyecto cuenta con una suite de 20 pruebas unitarias e integrales escritas para `pytest`.

Para ejecutar las pruebas:

```bash
# Crear entorno virtual e instalar pytest
python3 -m venv .venv
.venv/bin/pip install pytest

# Ejecutar test suite
.venv/bin/python3 -m pytest -v
```

---

## 🛡️ Reglas de Seguridad y Validación Cross-Platform

- **Inmutabilidad de Plantilla**: `Win64.rar` nunca se modifica en disco.
- **Transaccionalidad Sibling**: El staging temporal (`.destination.build-<uuid>`) se crea en el directorio padre de destino para evitar errores `EXDEV` entre distintas particiones (ext4, NTFS, exFAT).
- **Rollback Seguro**: En modo de reemplazo (`replace`), se crea un respaldo previo que se restaura automáticamente si ocurre cualquier error durante la copia.
- **Zip/Rar Slip Protection**: Se rechaza cualquier archivo en el RAR con rutas absolutas, secuencias `..`, caracteres UNC o enlaces simbólicos.
- **Sanitización Windows**: Se prohíben caracteres no válidos (`< > : " / \ | ? *`), nombres que terminen en punto o espacio (`"Game."`), y nombres de dispositivos reservados de Windows evaluando el *stem* case-insensitively incluso con extensión (`CON.exe`, `NUL.txt`).
