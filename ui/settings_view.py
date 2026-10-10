"""Pantalla de ajustes (idioma, versión, ubicación de datos y reinicio), dentro de la misma ventana."""
import os

import customtkinter as ctk
from tkinter import filedialog

import config
from config import APP_VERSION

LANGUAGES = {"English": "en", "Español": "es"}


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.cfg = app.cfg

        left_col = ctk.CTkFrame(self, fg_color="transparent")
        left_col.pack(side="left", anchor="n", padx=(0, 16))
        right_col = ctk.CTkFrame(self, fg_color="transparent")
        right_col.pack(side="left", anchor="n", fill="x", expand=True)

        card = ctk.CTkFrame(left_col, width=360)
        card.pack(anchor="nw")

        self.lbl_title = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_title.pack(anchor="w", padx=20, pady=(18, 10))

        self.lbl_lang = ctk.CTkLabel(card, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_lang.pack(anchor="w", padx=20)

        self.menu_lang = ctk.CTkOptionMenu(
            card, values=list(LANGUAGES), command=self._on_language_picked, width=180)
        self.menu_lang.pack(anchor="w", padx=20, pady=(6, 14))

        self.lbl_version = ctk.CTkLabel(card, text="", text_color="gray")
        self.lbl_version.pack(anchor="w", padx=20, pady=(0, 18))

        # --- Zona de "reinicio de la app" (mantiene los mods) ---
        danger_card = ctk.CTkFrame(left_col, width=360)
        danger_card.pack(anchor="nw", pady=(16, 0))

        self.lbl_danger_title = ctk.CTkLabel(danger_card, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_danger_title.pack(anchor="w", padx=20, pady=(18, 6))

        self.lbl_danger_hint = ctk.CTkLabel(danger_card, text="", text_color="gray", wraplength=320, justify="left")
        self.lbl_danger_hint.pack(anchor="w", padx=20, pady=(0, 12))

        self.btn_reset = ctk.CTkButton(
            danger_card, text="", fg_color="#a71d2a", hover_color="#842030",
            command=self._on_reset_clicked,
        )
        self.btn_reset.pack(anchor="w", padx=20, pady=(0, 18))

        # --- Ubicación de los datos (migrar perfiles fuera de AppData) ---
        loc_card = ctk.CTkFrame(right_col)
        loc_card.pack(anchor="nw", fill="x")

        self.lbl_loc_title = ctk.CTkLabel(loc_card, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_loc_title.pack(anchor="w", padx=20, pady=(18, 6))

        self.lbl_loc_hint = ctk.CTkLabel(loc_card, text="", text_color="gray", wraplength=400, justify="left")
        self.lbl_loc_hint.pack(anchor="w", padx=20, pady=(0, 12))

        self.lbl_loc_current = ctk.CTkLabel(loc_card, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_loc_current.pack(anchor="w", padx=20)
        self.lbl_loc_path = ctk.CTkLabel(loc_card, text="", wraplength=400, justify="left", anchor="w")
        self.lbl_loc_path.pack(anchor="w", padx=20, pady=(2, 12))

        self.lbl_loc_pick = ctk.CTkLabel(loc_card, text="", font=ctk.CTkFont(weight="bold"))
        self.lbl_loc_pick.pack(anchor="w", padx=20)
        pick_row = ctk.CTkFrame(loc_card, fg_color="transparent")
        pick_row.pack(fill="x", padx=20, pady=(6, 4))
        self.ent_loc = ctk.CTkEntry(pick_row)
        self.ent_loc.pack(side="left", fill="x", expand=True)
        self.ent_loc.bind("<KeyRelease>", lambda e: self._refresh_preview())
        self.btn_loc_browse = ctk.CTkButton(pick_row, text="", width=80, command=self._browse_location)
        self.btn_loc_browse.pack(side="left", padx=(8, 0))

        self.lbl_loc_preview = ctk.CTkLabel(loc_card, text="", text_color="gray", wraplength=400, justify="left", anchor="w")
        self.lbl_loc_preview.pack(anchor="w", padx=20, pady=(2, 10))

        btn_row = ctk.CTkFrame(loc_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 18))
        self.btn_loc_migrate = ctk.CTkButton(btn_row, text="", command=self._on_migrate_clicked)
        self.btn_loc_migrate.pack(side="left")
        self.btn_loc_default = ctk.CTkButton(btn_row, text="", fg_color="gray30", hover_color="gray25",
                                             command=self._on_default_clicked)
        self.btn_loc_default.pack(side="left", padx=(8, 0))

        self.apply_language()

    def apply_language(self):
        t = self.cfg.get_text
        self.lbl_title.configure(text=t("app_settings_title"))
        self.lbl_lang.configure(text=t("lang"))
        self.lbl_version.configure(text=t("version_label", version=APP_VERSION))
        current = self.cfg.data.get("language", "en")
        for name, code in LANGUAGES.items():
            if code == current:
                self.menu_lang.set(name)

        self.lbl_loc_title.configure(text=t("loc_title"))
        self.lbl_loc_hint.configure(text=t("loc_hint"))
        self.lbl_loc_current.configure(text=t("loc_current"))
        self.lbl_loc_pick.configure(text=t("loc_pick"))
        self.btn_loc_browse.configure(text=t("btn_browse"))
        self.btn_loc_migrate.configure(text=t("btn_loc_migrate"))
        self.btn_loc_default.configure(text=t("btn_loc_default"))
        self.refresh_location()

        self.lbl_danger_title.configure(text=t("reset_section_title"))
        self.lbl_danger_hint.configure(text=t("reset_section_hint"))
        self.btn_reset.configure(text=t("btn_reset_appdata"))

    def _on_language_picked(self, name):
        self.app.change_language(LANGUAGES[name])

    def _on_reset_clicked(self):
        t = self.cfg.get_text
        # Confirmación dentro de la ventana (banner), no un cuadro emergente.
        self.app.confirm(
            t("confirm_reset_msg"),
            on_yes=self.app.reset_app_data,
            title=t("confirm_reset_title"),
            yes_label=t("btn_reset_confirm"),
        )

    # ------------------------------------------------------------------
    # Ubicación de los datos
    # ------------------------------------------------------------------

    def _is_default_location(self):
        return os.path.normcase(os.path.abspath(config.DATA_DIR)) == os.path.normcase(os.path.abspath(config.BASE_DIR))

    def refresh_location(self):
        """Actualiza la carpeta actual y el estado de los botones."""
        t = self.cfg.get_text
        default = self._is_default_location()
        tag = f"  {t('loc_default_tag')}" if default else ""
        self.lbl_loc_path.configure(text=f"{config.DATA_DIR}{tag}")
        self.btn_loc_default.configure(state="disabled" if default else "normal")
        self._refresh_preview()

    def _chosen_root(self):
        """Carpeta final UE4ModLauncher para lo escrito en el campo, o None."""
        parent = self.ent_loc.get().strip().strip('"')
        if not parent:
            return None
        return config.location_root_for(parent)

    def _refresh_preview(self):
        root = self._chosen_root()
        t = self.cfg.get_text
        self.lbl_loc_preview.configure(text=t("loc_preview", path=os.path.join(root, "Profiles")) if root else "")
        self.btn_loc_migrate.configure(state="normal" if root else "disabled")

    def _browse_location(self):
        # Selector de carpetas del sistema (el explorador de Windows).
        path = filedialog.askdirectory()
        if path:
            self.ent_loc.delete(0, "end")
            self.ent_loc.insert(0, os.path.normpath(path))
            self._refresh_preview()

    def _on_migrate_clicked(self):
        t = self.cfg.get_text
        parent = self.ent_loc.get().strip().strip('"')
        if not parent or not os.path.isdir(parent):
            self.app.notify("error", t("loc_err_invalid"), title=t("err_title"))
            return
        root = config.location_root_for(parent)
        self._confirm_migration(root)

    def _on_default_clicked(self):
        self._confirm_migration(config.BASE_DIR)

    def _confirm_migration(self, root):
        t = self.cfg.get_text
        self.app.confirm(
            t("loc_confirm_msg", path=os.path.join(root, "Profiles")),
            on_yes=lambda: self.app.migrate_profiles(root),
            title=t("loc_confirm_title"),
            yes_label=t("btn_loc_confirm"),
        )
