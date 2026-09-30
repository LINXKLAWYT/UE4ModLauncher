# ENGLISH VERSION:

# UE4 Mod Launcher

A desktop launcher for games built with Unreal Engine 4 that manage
their mods using `.pak` files. Instead of manually copying and pasting mods
into the game's `~mods` folder every time you want to play (and removing
them afterward), the app handles this automatically, using a separate
profile for each game.

## What does it do?

- **Per-game profiles**: Each profile stores the path to the game's `.exe`,
the path to its `Paks` folder, and its own collection of mods.
- **Automatic deployment**: When you click "Play," the launcher moves the
profile's `.pak` files to the game's `~mods` folder, launches the executable,
waits for the game to close, and moves the mods back to the profile folder—
all without manual intervention.
- **Crash recovery**: If the launcher closes unexpectedly (crash, power
outage, forced close) while mods were deployed, it automatically recovers
them the next time it opens, rather than leaving them stranded in the
game folder.
- **In-app mod management**: Includes a button to add `.pak` files directly
(they are copied to the profile without altering the original) and another
to open the profile's mod folder in File Explorer.
- **Multilingual support**: Interface available in Spanish and English,
switchable via Settings.
- **AppData storage**: Profiles and settings are saved in
`%LOCALAPPDATA%\UE4ModLauncher`; it does not depend on the `.exe`
location or require administrator privileges.

## Optional Universal UE4 Unlocker (UUU) injection

The launcher allows for the optional use of **Universal UE4 Unlocker (UUU)**
via the settings for each profile. You can enable or disable the use of UUU
via the corresponding checkbox, so it is not necessary to use UUU
for every game.

The setting is saved with the game profile, meaning each profile
can have its own configuration.

## Update check

Every time the app starts it checks the latest release on GitHub in the
background. If a newer version exists, it offers to open the
[releases page](https://github.com/LINXKLAWYT/UE4ModLauncher/releases). If
you are offline or there is nothing new, nothing is shown. When you publish a
release, set `APP_VERSION` in `config.py` to the same number as the release tag.

## Requirements

- Python 3.10+ (only if running or compiling from source code)
- See `requirements.txt`:
- `customtkinter` — graphical interface
- `Pillow` — for displaying the logo within the application
- `psutil` *(optional, recommended)* — allows for more reliable detection
of when the game has actually closed, even for titles that use a
"launcher" executable that starts the actual game and then closes itself

## Usage

1. Open the application and click **➕ New** to create a profile.
2. Select it from the dropdown menu; its settings will appear on the right.
3. Enter the path to the game's `.exe` and its `Paks` folder, then press
**Save** (or simply switch profiles / close the application — it saves
automatically).
4. Use **➕ Add mods** to include your `.pak` files in the profile.
5. Click **▶ Start game**.

## Compiling the .exe

```
pyinstaller --noconfirm --clean --onefile --windowed --icon=icon.ico --add-data "logo.png;." --add-data "icon.ico;." --add-data "herramientas;herramientas" --name "UE4ModLauncher" main.py
```

The resulting executable is located at `dist\UE4ModLauncher.exe`. ## Project Structure

- `main.py` — Graphical interface (CustomTkinter)
- `core.py` — Profile logic, mod management, and game launching
- `config.py` — Data paths, bundled resources (logo/icon), and interface text
(ES/EN)

## License

This project is distributed under the MIT License. See the
[`LICENSE`](LICENSE) file for details.

## Disclaimer

This launcher is an unofficial third-party tool. It is not affiliated with
Epic Games or the developers of the games it supports. Using
mods may violate the terms of service of certain games —
please check the rules before use, especially for titles featuring anti-cheat
systems or competitive multiplayer.

# SPANISH VERSION:

# UE4 Mod Launcher

Un lanzador de escritorio para juegos hechos con Unreal Engine 4 que gestionan
sus mods mediante archivos `.pak`. En lugar de copiar y pegar mods a mano
dentro de la carpeta `~mods` del juego cada vez que quieres jugar (y volver a
sacarlos después), la app lo hace automáticamente, con un perfil independiente
por cada juego.

## ¿Qué hace?

- **Perfiles por juego**: cada perfil guarda la ruta al `.exe` del juego, la
  ruta a su carpeta `Paks`, y su propia colección de mods.
- **Despliegue automático**: al pulsar "Jugar", el launcher mueve los `.pak`
  del perfil a la carpeta `~mods` del juego, lanza el ejecutable, espera a que
  el juego se cierre y devuelve los mods a la carpeta del perfil — todo sin
  intervención manual.
- **Recuperación ante cierres inesperados**: si el launcher se cierra de
  golpe (crash, corte de luz, cierre forzado) mientras un juego tenía mods
  desplegados, la próxima vez que se abra los recupera automáticamente en
  vez de dejarlos perdidos dentro de la carpeta del juego.
- **Gestión de mods sin salir de la app**: botón para añadir archivos `.pak`
  directamente (se copian al perfil, sin tocar el original) y otro para abrir
  la carpeta de mods del perfil en el explorador de archivos.
- **Multilenguaje**: interfaz en español e inglés, cambiable desde Ajustes.
- **Datos en AppData**: los perfiles y ajustes se guardan en
  `%LOCALAPPDATA%\UE4ModLauncher`, no dependen de dónde se ejecute el `.exe`
  ni de permisos de administrador.
  
## Inyección opcional de Universal UE4 Unlocker (UUU)

El launcher permite usar **Universal UE4 Unlocker (UUU)** de forma opcional
desde los ajustes de cada perfil. Puedes activar o desactivar el uso de UUU
mediante la casilla correspondiente, por lo que no es necesario utilizar UUU
en todos los juegos.

La opción se guarda junto con el perfil del juego, de modo que cada perfil
puede tener su propia configuración.

## Buscar actualizaciones

Cada vez que abres la aplicación se comprueba en segundo plano la última
release de GitHub. Si hay una versión más nueva, te ofrece abrir la
[página de releases](https://github.com/LINXKLAWYT/UE4ModLauncher/releases).
Sin conexión o sin novedades no se muestra nada. Al publicar una release,
pon en `APP_VERSION` (`config.py`) el mismo número que el tag de la release.

## Requisitos

- Python 3.10+ (solo si se ejecuta o se compila desde el código fuente)
- Ver `requirements.txt`:
  - `customtkinter` — interfaz gráfica
  - `Pillow` — para mostrar el logo dentro de la app
  - `psutil` *(opcional, recomendado)* — permite detectar con más fiabilidad
    cuándo se ha cerrado realmente el juego, incluso en títulos que usan un
    ejecutable "lanzador" que arranca el juego real y se cierra solo

## Uso

1. Abre la app y pulsa **➕ Nuevo** para crear un perfil.
2. Selecciónalo en el desplegable: a la derecha aparecen sus ajustes.
3. Rellena la ruta del `.exe` del juego y la de su carpeta `Paks`, y pulsa
   **Guardar** (o simplemente cambia de perfil / cierra la app — se guarda
   solo).
4. Usa **➕ Añadir mods** para meter tus archivos `.pak` en el perfil.
5. Pulsa **▶ Iniciar juego**.

## Compilar el .exe

```
pyinstaller --noconfirm --clean --onefile --windowed --icon=icon.ico --add-data "logo.png;." --add-data "icon.ico;." --add-data "tools;tools" --name "UE4ModLauncher" main.py
```

El ejecutable resultante queda en `dist\UE4ModLauncher.exe`.

## Estructura del proyecto

- `main.py` — interfaz gráfica (CustomTkinter)
- `core.py` — lógica de perfiles, movimiento de mods y lanzamiento del juego
- `config.py` — rutas de datos, recursos empaquetados (logo/icono) y textos
  de la interfaz (ES/EN)

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo
[`LICENSE`](LICENSE) para más detalles.

## Aviso

Este launcher es una herramienta de terceros no oficial. No está afiliado a
Epic Games ni a los desarrolladores de los juegos con los que se use. El uso
de mods puede infringir los términos de servicio de algunos juegos —
infórmate antes de usarlo, especialmente en títulos con anti-cheat o
multijugador competitivo.
