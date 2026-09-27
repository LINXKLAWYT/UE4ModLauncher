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
pyinstaller --noconfirm --clean --onefile --windowed --icon=icon.ico --add-data "logo.png;." --add-data "icon.ico;." --name "UE4ModLauncher" main.py
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
