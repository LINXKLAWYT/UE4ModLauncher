"""Pantalla de ajustes (idioma y versión), dentro de la misma ventana."""
import customtkinter as ctk

from config import APP_VERSION

LANGUAGES = {"English": "en", "Español": "es"}


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.cfg = app.cfg

        card = ctk.CTkFrame(self, width=360)
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
        danger_card = ctk.CTkFrame(self, width=360)
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
