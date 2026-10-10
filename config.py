import os
import sys
import json


import shutil

APP_NAME = "UE4ModLauncher"

# Bump this on every release so it matches the tag you publish on GitHub
# (e.g. tag "v1.2.0" -> APP_VERSION = "1.2.0"); the update check compares them.
APP_VERSION = "1.6.0"
GITHUB_REPO = "LINXKLAWYT/UE4ModLauncher"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
# GitHub Pages site (docs/ folder on the main branch). The help/support
# page now lives under /help/ - the site root is the marketing page.
# Update this if the GitHub username or repo name ever changes.
HELP_URL = "https://linxklawyt.github.io/UE4ModLauncher/help.html"


def get_base_dir():
    """
    Directory where the settings file lives (and, by default, Profiles/ and
    the crash-recovery state file): a per-user AppData folder, e.g.
    C:\\Users\\<you>\\AppData\\Local\\UE4ModLauncher

    This is the standard place for a Windows app to keep its own data, and
    it sidesteps the problems relative/exe-adjacent paths had: it doesn't
    depend on the current working directory (which can change unexpectedly
    when running elevated), and it survives moving, renaming or
    reinstalling the .exe itself.

    NOTE: this is deliberately separate from get_resource_path() below -
    this is for the user's own data (must persist, must be writable);
    that one is for read-only assets baked into the .exe (logo.png,
    icon.ico) via --add-data, which live wherever PyInstaller unpacks them.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def _get_legacy_base_dir():
    """Where data used to live (next to the script/.exe), kept only so
    existing profiles can be migrated automatically on first run."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
os.makedirs(BASE_DIR, exist_ok=True)

# Settings and the "where is my data" pointer always stay in AppData: the
# app has to find them before it knows where the profiles are.
MAIN_CONFIG_FILE = os.path.join(BASE_DIR, "launcher_settings.json")
LOCATION_FILE = os.path.join(BASE_DIR, "data_location.json")

# Profiles/ and the crash-recovery state live in DATA_DIR: AppData by
# default, or a folder named UE4ModLauncher somewhere else if the user
# migrated them. Other modules must read these as `config.PROFILES_DIR` /
# `config.STATE_FILE` (not `from config import ...`) so a migration takes
# effect without restarting the app.
DATA_DIR = BASE_DIR
PROFILES_DIR = os.path.join(DATA_DIR, "Profiles")
STATE_FILE = os.path.join(DATA_DIR, "launcher_state.json")
LOCATION_PROBLEM = None   # custom folder that was configured but is unreachable


def location_root_for(parent):
    """Final data folder for a folder chosen by the user: <parent>/UE4ModLauncher,
    unless the chosen folder is already called UE4ModLauncher."""
    parent = os.path.abspath(parent)
    if os.path.basename(parent.rstrip("\\/")).lower() == APP_NAME.lower():
        return parent
    return os.path.join(parent, APP_NAME)


def apply_data_dir(root):
    """Point the data paths at `root` (takes effect immediately)."""
    global DATA_DIR, PROFILES_DIR, STATE_FILE
    DATA_DIR = root
    PROFILES_DIR = os.path.join(root, "Profiles")
    STATE_FILE = os.path.join(root, "launcher_state.json")


def read_location_pointer():
    try:
        with open(LOCATION_FILE, 'r', encoding='utf-8') as f:
            path = json.load(f).get("path")
        return path if isinstance(path, str) and path else None
    except (OSError, ValueError, AttributeError):
        return None


def write_location_pointer(root):
    """Remember a custom data folder; None goes back to the AppData default."""
    if root is None or os.path.normcase(os.path.abspath(root)) == os.path.normcase(BASE_DIR):
        try:
            if os.path.exists(LOCATION_FILE):
                os.remove(LOCATION_FILE)
        except OSError:
            return False
        return True
    try:
        with open(LOCATION_FILE, 'w', encoding='utf-8') as f:
            json.dump({"path": os.path.abspath(root)}, f, indent=4)
        return True
    except OSError:
        return False


def _init_data_dir():
    global LOCATION_PROBLEM
    root = read_location_pointer()
    if root and os.path.isdir(root):
        apply_data_dir(root)
    elif root:
        # Drive unplugged / folder deleted: fall back to AppData for this
        # session instead of crashing, and let the UI warn about it.
        LOCATION_PROBLEM = root


_init_data_dir()


def _migrate_legacy_data():
    """One-time migration: if profiles/settings exist next to the old
    script/exe location but not yet in AppData, move them over instead of
    the user's profiles silently "disappearing" after this update."""
    legacy_base = _get_legacy_base_dir()
    if os.path.normcase(legacy_base) == os.path.normcase(BASE_DIR):
        return

    legacy_profiles = os.path.join(legacy_base, "Profiles")
    legacy_config = os.path.join(legacy_base, "launcher_settings.json")
    legacy_state = os.path.join(legacy_base, "launcher_state.json")

    try:
        if os.path.isdir(legacy_profiles) and not os.path.exists(PROFILES_DIR):
            shutil.move(legacy_profiles, PROFILES_DIR)
        if os.path.isfile(legacy_config) and not os.path.exists(MAIN_CONFIG_FILE):
            shutil.move(legacy_config, MAIN_CONFIG_FILE)
        if os.path.isfile(legacy_state) and not os.path.exists(STATE_FILE):
            shutil.move(legacy_state, STATE_FILE)
    except OSError:
        pass  # best effort - worst case, the user keeps two copies


_migrate_legacy_data()


def get_resource_path(relative_path):
    """
    Path to a resource that is EMBEDDED INSIDE the compiled .exe (via
    PyInstaller's --add-data), such as logo.png or icon.ico. This is
    deliberately separate from BASE_DIR: BASE_DIR is for files the user
    can see and that must persist next to the .exe (Profiles/, settings),
    while this is for read-only assets baked into the binary itself.

    When PyInstaller builds with --onefile, everything passed via
    --add-data is unpacked at startup into a temporary folder, whose path
    it exposes as sys._MEIPASS. In development (running main.py directly
    with Python) there is no such folder, so we just read the file from
    next to this script instead.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


LOGO_PNG = get_resource_path("logo.png")   # logo mostrado dentro de la app
ICON_ICO = get_resource_path("icon.ico")   # icono del .exe / barra de tareas

# ==========================================
# LANGUAGE DICTIONARY (EN / ES) - DEFAULT: EN
# ==========================================
LANG = {
    "en": {
        "title": "UE4 Mod Launcher",
        "play": "▶ LAUNCH GAME",
        "settings": "⚙ Settings",
        "profile": "Active Game Profile:",
        "mods_list": "Mods in current profile:",
        "no_mods": "No mods found.",
        "cfg_title": "Profile Settings",
        "cfg_exe": "Game .exe Path:",
        "cfg_paks": "Game 'Paks' Folder Path:",
        "cfg_uuu": "Use Universal UE4 Unlocker (UUU)",
        "cfg_uuu_dll": "UUU .dll file (UniversalUE4Unlocker.dll):",
        "err_uuu_dll": "To use UUU, select its .dll file with the Browse button.",
        "btn_browse": "Browse",
        "btn_save": "Save",
        "btn_delete": "🗑 Delete",
        "btn_new": "➕ New",
        "lang": "Language:",
        "err_fields": "Please fill in both paths.",
        "new_prof_title": "New Profile",
        "new_prof_msg": "Enter profile name:",
        "err_exists": "Profile already exists.",
        "status_ready": "Ready to launch.",
        "status_playing": "Game running…",
        "err_launch_title": "Launch error",
        "err_exe_missing": "The configured .exe path no longer exists. Check its settings.",
        "err_paks_missing": "The configured 'Paks' folder no longer exists. Check its settings.",
        "err_launch_generic": "Could not launch the game.\n\n{error}",
        "err_partial_move": "The game closed, but some mod files could not be moved automatically:\n{files}\n\nPlease check them manually in the profile's Mods folder or the game's ~mods folder.",
        "recovered_title": "Mods recovered",
        "recovered_msg": "The launcher was closed unexpectedly during a previous session.\n{count} mod file(s) were found in the game folder and moved back into the profile.",
        "recovery_failed_msg": "Could not fully recover mods left over from a previous session (profile '{profile}'). Please check the game's ~mods folder manually.",
        "confirm_delete_title": "Delete profile",
        "confirm_delete_msg": "Delete profile '{name}' and all its local mod files? This cannot be undone.",
        "invalid_profile_name": "That name isn't valid for a folder. Please use a different profile name.",
        "btn_open_folder": "📂 Open",
        "btn_add_mods": "➕ Add mods",
        "btn_refresh_mods": "🔄 Refresh mods",
        "mods_selection_hint": "Select the mods you want to activate when launching the game.",
        "err_no_profile": "Create a profile first with the '➕ New' button.",
        "err_open_folder": "Could not open the folder.",
        "err_copy_mods": "Could not copy the following file(s):\n{files}",
        "update_title": "Update available",
        "update_msg": "A new version is available: {latest} (you have {current}).\n\nOpen the download page on GitHub?",
        "btn_create": "Create",
        "btn_cancel": "Cancel",
        "btn_yes": "Yes",
        "btn_no": "No",
        "btn_back": "← Back",
        "btn_download": "Download",
        "btn_later": "Later",
        "btn_delete_confirm": "Delete",
        "new_prof_placeholder": "Profile name",
        "err_title": "Error",
        "profile_created": "Profile '{name}' created.",
        "profile_deleted": "Profile '{name}' deleted.",
        "update_msg_short": "New version available: {latest} (you have {current}).",
        "version_label": "Version {version}",
        "loc_title": "Data location",
        "loc_hint": "Profiles and their mods are kept in a folder named UE4ModLauncher. You can move it out of AppData to another folder or drive.",
        "loc_current": "Current folder:",
        "loc_default_tag": "(AppData, default)",
        "loc_pick": "Move to this folder:",
        "loc_preview": "Profiles will be stored in:\n{path}",
        "btn_loc_migrate": "Migrate profiles",
        "btn_loc_default": "Back to AppData",
        "loc_confirm_title": "Migrate profiles?",
        "loc_confirm_msg": "Profiles and their mods will be copied to:\n{path}\nand, once the copy is verified, removed from the current location.",
        "btn_loc_confirm": "Migrate",
        "loc_busy": "Migrating profiles… wait until it finishes.",
        "loc_done_title": "Migration finished",
        "loc_err_unexpected": "Unexpected error while migrating: {detail}",
        "loc_done": "Profiles migrated to:\n{path}\n{count} profile(s) moved.",
        "loc_done_leftover": "Profiles migrated to:\n{path}\nThe old folder could not be fully deleted (some files may be in use).",
        "loc_err_invalid": "Choose an existing folder first.",
        "loc_err_same": "That is already the current location.",
        "loc_err_nested": "The new location can't be inside the current Profiles folder.",
        "loc_err_pending": "Can't migrate now: mods from an unfinished session are still in the game folder. Restart the launcher so it can recover them, then try again.",
        "loc_err_writable": "Can't write to that folder. Pick another one.\n{detail}",
        "loc_err_notempty": "That location already contains profiles:\n{path}\nPick another folder or empty it first.",
        "loc_err_copy": "The copy failed; nothing was changed.\n{detail}",
        "loc_err_verify": "The copy could not be verified; nothing was changed.",
        "loc_err_pointer": "The new location could not be saved; nothing was changed.",
        "loc_missing": "The custom data folder is not available:\n{path}\nThe launcher is using AppData for now. Reconnect the drive and restart it to use that folder again.",
        "app_settings_title": "Settings",
        "no_profile_panel_hint": "No profile selected",
        "reset_section_title": "Reset app data",
        "reset_section_hint": "Deletes all settings and profile configuration (exe/paks paths, language) and recreates everything from scratch. Each profile's mods are kept.",
        "btn_reset_appdata": "🗑 Reset app data",
        "confirm_reset_title": "Reset app data?",
        "confirm_reset_msg": "This deletes all settings and profile configuration and recreates them from scratch. Each profile's mods will be kept. This cannot be undone.",
        "btn_reset_confirm": "Reset",
        "reset_failed": "Could not reset app data.\n\n{error}",
        "reset_done": "App data reset. {count} profile(s) kept their mods.",
        "btn_help": "❓ Help",
    },
    "es": {
        "title": "Lanzador de mods en UE4",
        "play": "▶ INICIAR JUEGO",
        "settings": "⚙ Ajustes",
        "profile": "Perfil Activo:",
        "mods_list": "Mods en este perfil:",
        "no_mods": "No se encontraron mods.",
        "cfg_title": "Ajustes del perfil",
        "cfg_exe": "Ruta del ejecutable (.exe):",
        "cfg_paks": "Ruta de la carpeta 'Paks':",
        "cfg_uuu": "Usar Universal UE4 Unlocker (UUU)",
        "cfg_uuu_dll": "Archivo .dll del UUU (UniversalUE4Unlocker.dll):",
        "err_uuu_dll": "Para usar el UUU, selecciona su archivo .dll con el botón Buscar.",
        "btn_browse": "Buscar",
        "btn_save": "Guardar",
        "btn_delete": "🗑 Eliminar",
        "btn_new": "➕ Nuevo",
        "lang": "Idioma:",
        "err_fields": "Faltan rutas por rellenar.",
        "new_prof_title": "Nuevo Perfil",
        "new_prof_msg": "Nombre del perfil:",
        "err_exists": "El perfil ya existe.",
        "status_ready": "Listo para jugar.",
        "status_playing": "Juego en ejecución…",
        "err_launch_title": "Error al iniciar",
        "err_exe_missing": "La ruta del .exe configurada ya no existe. Revisa sus ajustes.",
        "err_paks_missing": "La carpeta 'Paks' configurada ya no existe. Revisa sus ajustes.",
        "err_launch_generic": "No se pudo iniciar el juego.\n\n{error}",
        "err_partial_move": "El juego se cerró, pero algunos mods no se pudieron mover automáticamente:\n{files}\n\nRevísalos manualmente en la carpeta Mods del perfil o en la carpeta ~mods del juego.",
        "recovered_title": "Mods recuperados",
        "recovered_msg": "El lanzador se cerró inesperadamente durante una sesión anterior.\nSe encontraron {count} mod(s) en la carpeta del juego y se movieron de vuelta al perfil.",
        "recovery_failed_msg": "No se pudieron recuperar todos los mods de una sesión anterior (perfil '{profile}'). Revisa la carpeta ~mods del juego manualmente.",
        "confirm_delete_title": "Eliminar perfil",
        "confirm_delete_msg": "¿Eliminar el perfil '{name}' y todos sus mods locales? Esta acción no se puede deshacer.",
        "invalid_profile_name": "Ese nombre no es válido para una carpeta. Usa otro nombre de perfil.",
        "btn_open_folder": "📂 Abrir",
        "btn_add_mods": "➕ Añadir mods",
        "btn_refresh_mods": "🔄 Recargar mods",
        "mods_selection_hint": "Marca los mods que quieras activar al jugar.",
        "err_no_profile": "Crea un perfil primero con el botón '➕ Nuevo'.",
        "err_open_folder": "No se pudo abrir la carpeta.",
        "err_copy_mods": "No se pudieron copiar estos archivos:\n{files}",
        "update_title": "Actualización disponible",
        "update_msg": "Hay una nueva versión disponible: {latest} (tienes la {current}).\n\n¿Abrir la página de descargas en GitHub?",
        "btn_create": "Crear",
        "btn_cancel": "Cancelar",
        "btn_yes": "Sí",
        "btn_no": "No",
        "btn_back": "← Volver",
        "btn_download": "Descargar",
        "btn_later": "Más tarde",
        "btn_delete_confirm": "Eliminar",
        "new_prof_placeholder": "Nombre del perfil",
        "err_title": "Error",
        "profile_created": "Perfil '{name}' creado.",
        "profile_deleted": "Perfil '{name}' eliminado.",
        "update_msg_short": "Nueva versión disponible: {latest} (tienes la {current}).",
        "version_label": "Versión {version}",
        "loc_title": "Ubicación de los datos",
        "loc_hint": "Los perfiles y sus mods se guardan en una carpeta llamada UE4ModLauncher. Puedes sacarla de AppData y llevarla a otra carpeta o disco.",
        "loc_current": "Carpeta actual:",
        "loc_default_tag": "(AppData, por defecto)",
        "loc_pick": "Mover a esta carpeta:",
        "loc_preview": "Los perfiles se guardarán en:\n{path}",
        "btn_loc_migrate": "Migrar perfiles",
        "btn_loc_default": "Volver a AppData",
        "loc_confirm_title": "¿Migrar los perfiles?",
        "loc_confirm_msg": "Los perfiles y sus mods se copiarán a:\n{path}\ny, cuando la copia esté verificada, se quitarán de la ubicación actual.",
        "btn_loc_confirm": "Migrar",
        "loc_busy": "Migrando perfiles… espera a que termine.",
        "loc_done_title": "Migración terminada",
        "loc_err_unexpected": "Error inesperado al migrar: {detail}",
        "loc_done": "Perfiles migrados a:\n{path}\n{count} perfil(es) movidos.",
        "loc_done_leftover": "Perfiles migrados a:\n{path}\nNo se pudo borrar del todo la carpeta anterior (puede que haya archivos en uso).",
        "loc_err_invalid": "Elige primero una carpeta que exista.",
        "loc_err_same": "Esa ya es la ubicación actual.",
        "loc_err_nested": "La nueva ubicación no puede estar dentro de la carpeta Profiles actual.",
        "loc_err_pending": "No se puede migrar ahora: quedan mods de una sesión sin cerrar en la carpeta del juego. Reinicia el launcher para que los recupere y vuelve a intentarlo.",
        "loc_err_writable": "No se puede escribir en esa carpeta. Elige otra.\n{detail}",
        "loc_err_notempty": "Esa ubicación ya contiene perfiles:\n{path}\nElige otra carpeta o vacíala primero.",
        "loc_err_copy": "La copia falló; no se cambió nada.\n{detail}",
        "loc_err_verify": "No se pudo verificar la copia; no se cambió nada.",
        "loc_err_pointer": "No se pudo guardar la nueva ubicación; no se cambió nada.",
        "loc_missing": "La carpeta de datos personalizada no está disponible:\n{path}\nEl launcher usa AppData por ahora. Reconecta el disco y reinícialo para volver a usar esa carpeta.",
        "app_settings_title": "Ajustes",
        "no_profile_panel_hint": "Ningún perfil seleccionado",
        "reset_section_title": "Restaurar datos de la app",
        "reset_section_hint": "Elimina todos los ajustes y la configuración de los perfiles (rutas de exe/paks, idioma) y lo recrea todo desde cero. Los mods de cada perfil se conservan.",
        "btn_reset_appdata": "🗑 Restaurar datos de la app",
        "confirm_reset_title": "¿Restaurar datos de la app?",
        "confirm_reset_msg": "Esto elimina todos los ajustes y la configuración de los perfiles y lo recrea todo desde cero. Los mods de cada perfil se conservarán. Esta acción no se puede deshacer.",
        "btn_reset_confirm": "Restaurar",
        "reset_failed": "No se pudieron restaurar los datos de la app.\n\n{error}",
        "reset_done": "Datos de la app restaurados. {count} perfil(es) conservaron sus mods.",
        "btn_help": "❓ Ayuda",
    }
}

class ConfigManager:
    def __init__(self):
        # Default configuration settings
        self.data = {"language": "en", "last_profile": ""}
        self.load()

    def load(self):
        # Load configuration if the file exists
        if os.path.exists(MAIN_CONFIG_FILE):
            try:
                with open(MAIN_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.data.update(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass  # fall back to defaults rather than crash on a corrupt file

    def save(self):
        # Save current configuration to the JSON file
        with open(MAIN_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)

    def get_text(self, key, **kwargs):
        # Return text based on the currently selected language, optionally
        # filling in {placeholders} (e.g. get_text("recovered_msg", count=3))
        text = LANG.get(self.data["language"], LANG["en"]).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text