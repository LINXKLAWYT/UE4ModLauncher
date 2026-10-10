"""
Ventana principal. Una sola ventana con dos pantallas (Inicio y Ajustes) y
una barra de avisos; no se abre ninguna ventana aparte.
"""
import os
import queue
import threading
import webbrowser

import customtkinter as ctk
from PIL import Image

import updater
import config
from config import ConfigManager, LOGO_PNG, ICON_ICO, APP_VERSION, HELP_URL
from core import ModLogic
from ui.banner import NotificationBar
from ui.home_view import HomeView
from ui.settings_view import SettingsView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ModLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        ModLogic.ensure_directories()
        self.cfg = ConfigManager()

        self._update_queue = queue.Queue()  # hilo de actualizaciones -> hilo principal
        self._migration_queue = queue.Queue()  # hilo de migración -> hilo principal
        self.migrating = False              # True mientras se migran los perfiles
        self._current_view = "home"

        self.title(self.cfg.get_text("title"))
        self.geometry("920x800")
        self.resizable(False, False)
        self._set_window_icon(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_top_bar()

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # La barra de avisos aparece justo encima del contenido.
        self.banner = NotificationBar(self, before=self.body)

        self.home = HomeView(self.body, self)
        self.settings_view = SettingsView(self.body, self)
        self.show_view("home")

        # Si el launcher se cerró a la fuerza con mods desplegados en la
        # carpeta del juego, recuperarlos ahora.
        self.after(300, self._check_recovery)
        # Avisar si la carpeta de datos personalizada no está disponible.
        self.after(600, self._check_location)
        # Buscar versión nueva en GitHub (hilo aparte, nunca bloquea la UI).
        self.after(1200, self._start_update_check)

    # ==================================================================
    # Estructura
    # ==================================================================

    @staticmethod
    def _set_window_icon(window):
        if os.path.exists(ICON_ICO):
            try:
                window.iconbitmap(ICON_ICO)
            except Exception:
                pass

    def _build_top_bar(self):
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=20, pady=15)

        self.logo_image = None
        if os.path.exists(LOGO_PNG):
            try:
                pil_logo = Image.open(LOGO_PNG)
                self.logo_image = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(56, 56))
                self.lbl_logo = ctk.CTkLabel(self.top_frame, image=self.logo_image, text="")
                self.lbl_logo.pack(side="left", padx=(0, 12))
            except Exception:
                self.logo_image = None

        self.lbl_title = ctk.CTkLabel(self.top_frame, text=self.cfg.get_text("title"), font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.pack(side="left")

        # Este botón alterna entre "Ajustes" (en Inicio) y "Volver" (en Ajustes).
        self.btn_settings = ctk.CTkButton(self.top_frame, text="", width=100)
        self.btn_settings.pack(side="right")

        # Abre la ayuda alojada en GitHub Pages en el navegador - ya no
        # depende de un archivo .html local empaquetado con la app.
        self.btn_help = ctk.CTkButton(
            self.top_frame, text=self.cfg.get_text("btn_help"), width=90,
            fg_color="gray30", hover_color="gray25",
            command=lambda: webbrowser.open(HELP_URL),
        )
        self.btn_help.pack(side="right", padx=(0, 8))

    def show_view(self, name):
        self.home.pack_forget()
        self.settings_view.pack_forget()
        if name == "settings":
            self.home.persist()  # guardar lo escrito antes de salir de Inicio
            self.settings_view.refresh_location()
            self.settings_view.pack(fill="both", expand=True)
        else:
            self.home.pack(fill="both", expand=True)
        self._current_view = name
        self._refresh_top_button()

    def _refresh_top_button(self):
        if self._current_view == "settings":
            self.btn_settings.configure(text=self.cfg.get_text("btn_back"), command=lambda: self.show_view("home"))
        else:
            self.btn_settings.configure(text=self.cfg.get_text("settings"), command=lambda: self.show_view("settings"))

    # ==================================================================
    # Avisos y confirmaciones (en lugar de cuadros emergentes)
    # ==================================================================

    def notify(self, kind, text, title="", actions=None, sticky=False, key=None):
        self.banner.push(kind, text, title=title, actions=actions, sticky=sticky, key=key)

    def confirm(self, text, on_yes, title="", yes_label=None, no_label=None):
        t = self.cfg.get_text
        self.banner.push(
            "question", text, title=title,
            actions=[(yes_label or t("btn_yes"), on_yes), (no_label or t("btn_no"), None)],
        )

    # ==================================================================
    # Recuperación tras un cierre inesperado
    # ==================================================================

    def _check_recovery(self):
        recovery = ModLogic.recover_pending_state()
        if recovery is None:
            return
        t = self.cfg.get_text
        if recovery["recovered"]:
            self.notify("info", t("recovered_msg", count=len(recovery["recovered"])),
                        title=t("recovered_title"), sticky=True)
            self.home.load_mods_list()
        elif recovery["failed"]:
            self.notify("warning", t("recovery_failed_msg", profile=recovery.get("profile", "")),
                        title=t("recovered_title"))

    def _check_location(self):
        if config.LOCATION_PROBLEM:
            self.notify("warning", self.cfg.get_text("loc_missing", path=config.LOCATION_PROBLEM),
                        title=self.cfg.get_text("loc_title"), sticky=True)

    # ==================================================================
    # Migrar los perfiles a otra ubicación
    # ==================================================================

    def migrate_profiles(self, new_root):
        if self.migrating:
            return
        self.home.persist()  # no perder lo escrito en los campos del perfil
        self.migrating = True
        self.notify("info", self.cfg.get_text("loc_busy"), sticky=True, key="migration")
        threading.Thread(target=self._migration_worker, args=(new_root,), daemon=True).start()
        self.after(300, self._poll_migration)

    def _migration_worker(self, new_root):
        try:
            result = ModLogic.migrate_profiles(new_root)
        except Exception as e:  # nunca dejar la app esperando para siempre
            result = {"success": False, "error": "unexpected", "detail": str(e),
                      "root": new_root, "profiles": 0}
        self._migration_queue.put(result)

    def _poll_migration(self):
        try:
            result = self._migration_queue.get_nowait()
        except queue.Empty:
            self.after(300, self._poll_migration)
            return
        self.migrating = False
        self._on_migration_done(result)

    def _on_migration_done(self, result):
        t = self.cfg.get_text
        self.banner.resolve("migration")  # quitar el "migrando…"
        err = result.get("error")
        if err:
            msgs = {
                "unexpected": t("loc_err_unexpected", detail=result.get("detail", "")),
                "same_location": t("loc_err_same"),
                "nested": t("loc_err_nested"),
                "pending_state": t("loc_err_pending"),
                "not_writable": t("loc_err_writable", detail=result.get("detail", "")),
                "target_not_empty": t("loc_err_notempty", path=os.path.join(result["root"], "Profiles")),
                "copy_failed": t("loc_err_copy", detail=result.get("detail", "")),
                "verify_failed": t("loc_err_verify"),
                "pointer_failed": t("loc_err_pointer"),
            }
            self.notify("error", msgs.get(err, err), title=t("err_title"), sticky=True)
            return

        # Las rutas ya apuntan a la nueva carpeta: volver a leer perfiles y mods.
        self.home.update_profile_dropdown()
        self.home.load_mods_list()
        self.settings_view.ent_loc.delete(0, "end")
        self.settings_view.refresh_location()
        path = os.path.join(result["root"], "Profiles")
        if result.get("leftover"):
            self.notify("warning", t("loc_done_leftover", path=path), sticky=True)
        else:
            self.notify("success", t("loc_done", path=path, count=result["profiles"]),
                        title=t("loc_done_title"), sticky=True)

    # ==================================================================
    # Buscar actualizaciones
    # ==================================================================

    def _start_update_check(self):
        threading.Thread(
            target=lambda: self._update_queue.put(updater.check_for_update()),
            daemon=True,
        ).start()
        self.after(500, self._poll_update_result)

    def _poll_update_result(self):
        try:
            info = self._update_queue.get_nowait()
        except queue.Empty:
            self.after(500, self._poll_update_result)
            return
        if not info:
            return
        t = self.cfg.get_text
        self.notify(
            "info",
            t("update_msg_short", latest=info["latest"], current=APP_VERSION),
            title=t("update_title"),
            actions=[
                (t("btn_download"), lambda: webbrowser.open(info["url"])),
                (t("btn_later"), None),
            ],
        )

    # ==================================================================
    # Restaurar datos de la app (conservando los mods)
    # ==================================================================

    def reset_app_data(self):
        self.home.persist()  # por si había cambios en curso, antes de borrarlo todo
        self.notify("info", self.cfg.get_text("reset_section_title"), sticky=True, key="reset")
        threading.Thread(target=self._reset_worker, daemon=True).start()

    def _reset_worker(self):
        try:
            result = ModLogic.reset_appdata_keep_mods()
        except Exception as e:
            result = {"success": False, "error": str(e), "profiles": []}
        self.after(0, lambda: self._on_reset_done(result))

    def _on_reset_done(self, result):
        self.banner.resolve("reset")
        if not result["success"]:
            self.notify(
                "error",
                self.cfg.get_text("reset_failed", error=result.get("error", "")),
                title=self.cfg.get_text("err_title"),
            )
            return

        # El archivo de ajustes se borró y se volvió a crear con los
        # valores por defecto - recargarlo en memoria también.
        self.cfg = ConfigManager()
        self.home.cfg = self.cfg
        self.settings_view.cfg = self.cfg

        self.title(self.cfg.get_text("title"))
        self.lbl_title.configure(text=self.cfg.get_text("title"))
        self.btn_help.configure(text=self.cfg.get_text("btn_help"))
        self._refresh_top_button()
        self.home.update_profile_dropdown()
        self.home.load_mods_list()
        self.home.apply_language()
        self.settings_view.apply_language()

        self.notify("success", self.cfg.get_text("reset_done", count=len(result["profiles"])), sticky=True)

    # ==================================================================
    # Idioma y cierre
    # ==================================================================

    def change_language(self, selected_lang):
        self.cfg.data["language"] = selected_lang
        self.cfg.save()

        self.title(self.cfg.get_text("title"))
        self.lbl_title.configure(text=self.cfg.get_text("title"))
        self.btn_help.configure(text=self.cfg.get_text("btn_help"))
        self._refresh_top_button()
        self.home.apply_language()
        self.settings_view.apply_language()

    def _on_close(self):
        # No perder cambios en curso al cerrar la ventana.
        self.home.persist()
        self.destroy()