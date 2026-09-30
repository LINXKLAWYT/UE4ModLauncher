import os
import re
import json
import queue
import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox, filedialog, simpledialog
from PIL import Image
from config import ConfigManager, PROFILES_DIR, LOGO_PNG, ICON_ICO, APP_VERSION
from core import ModLogic
import updater

# Global visual configuration for CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


class ModLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Initialize core logic and config manager
        ModLogic.ensure_directories()
        self.cfg = ConfigManager()

        self._mods_poll_id = None      # tracks the mods-list auto-refresh timer
        self._result_queue = queue.Queue()  # worker thread -> main thread handoff
        self._current_profile = None   # profile whose fields are currently shown on the right
        self._update_queue = queue.Queue()  # update-check thread -> main thread

        # Main window setup
        self.title(self.cfg.get_text("title"))
        self.geometry("920x800")
        self.resizable(False, False)
        self._set_window_icon(self)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.setup_ui()
        self.update_profile_dropdown()
        self.load_mods_list()

        # If the launcher was killed/crashed while a game had mods deployed
        # in its folder, recover them now instead of leaving them stranded.
        self.after(300, self._check_recovery)

        # Look for a newer release on GitHub (background thread, never blocks the UI).
        self.after(1200, self._start_update_check)

    @staticmethod
    def _set_window_icon(window):
        """
        Fija el icono de la ventana (se ve en la barra de título y, en
        Windows, también en la barra de tareas). Es "best effort": si el
        archivo icon.ico no existe todavía, o el sistema operativo no
        soporta .ico (p. ej. Linux), simplemente no hace nada en vez de
        romper el arranque de la app.
        """
        if os.path.exists(ICON_ICO):
            try:
                window.iconbitmap(ICON_ICO)
            except Exception:
                pass

    # ==================================================================
    # UI layout
    # ==================================================================

    def setup_ui(self):
        # --- Top Bar: logo, title, settings (language) ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=20, pady=15)

        # Logo de la app (opcional): si logo.png existe se muestra a la
        # izquierda del título; si no existe todavía, se omite sin error.
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

        # Settings now only holds the language switch - profile creation and
        # profile settings live directly on the home screen (see below).
        self.btn_settings = ctk.CTkButton(self.top_frame, text=self.cfg.get_text("settings"), width=100, command=self.open_settings)
        self.btn_settings.pack(side="right")

        # --- Body: left = pick/play, right = settings for the picked profile ---
        self.body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.left_frame = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.right_frame = ctk.CTkFrame(self.body_frame, width=300)
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.pack_propagate(False)  # keep a fixed width regardless of content

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        # --- Profile Selector + New/Delete ---
        self.prof_frame = ctk.CTkFrame(self.left_frame)
        self.prof_frame.pack(fill="x", pady=(0, 10))

        self.lbl_profile = ctk.CTkLabel(self.prof_frame, text=self.cfg.get_text("profile"), font=ctk.CTkFont(weight="bold"))
        self.lbl_profile.pack(anchor="w", padx=15, pady=(10, 0))

        prof_row = ctk.CTkFrame(self.prof_frame, fg_color="transparent")
        prof_row.pack(fill="x", padx=15, pady=(5, 10))

        self.combo_profiles = ctk.CTkOptionMenu(prof_row, values=["---"], command=self.on_profile_change, width=170)
        self.combo_profiles.pack(side="left")

        self.btn_new_profile = ctk.CTkButton(prof_row, text=self.cfg.get_text("btn_new"), width=80, command=self.create_new_profile)
        self.btn_new_profile.pack(side="left", padx=(8, 0))

        self.btn_delete_profile = ctk.CTkButton(prof_row, text=self.cfg.get_text("btn_delete"), width=90, fg_color="#a71d2a", hover_color="#842030", command=self.delete_selected_profile)
        self.btn_delete_profile.pack(side="left", padx=(8, 0))

        mods_row = ctk.CTkFrame(self.prof_frame, fg_color="transparent")
        mods_row.pack(fill="x", padx=15, pady=(0, 10))

        self.btn_open_folder = ctk.CTkButton(mods_row, text=self.cfg.get_text("btn_open_folder"), width=100, command=self.open_profile_folder)
        self.btn_open_folder.pack(side="left")

        self.btn_add_mods = ctk.CTkButton(mods_row, text=self.cfg.get_text("btn_add_mods"), width=150, command=self.add_mods_dialog)
        self.btn_add_mods.pack(side="left", padx=(8, 0))

        # --- Mods List ---
        self.mods_frame = ctk.CTkFrame(self.left_frame)
        self.mods_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_mods = ctk.CTkLabel(self.mods_frame, text=self.cfg.get_text("mods_list"))
        self.lbl_mods.pack(anchor="w", padx=15, pady=(10, 5))

        self.textbox_mods = ctk.CTkTextbox(self.mods_frame, state="disabled", fg_color="#1e1e1e", text_color="#00FF00")
        self.textbox_mods.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # --- Play Button ---
        self.btn_play = ctk.CTkButton(self.left_frame, text=self.cfg.get_text("play"), height=50, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#28a745", hover_color="#218838", command=self.play_game)
        self.btn_play.pack(fill="x")

    def _build_right_panel(self):
        """Shows exe/paks/process settings for whichever profile is
        currently selected in the left panel's dropdown. Updates every
        time the selection changes (on_profile_change -> refresh_profile_panel)."""
        self.lbl_profile_settings = ctk.CTkLabel(self.right_frame, text=self.cfg.get_text("cfg_title"), font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_profile_settings.pack(anchor="w", padx=15, pady=(15, 0))

        self.lbl_profile_settings_sub = ctk.CTkLabel(self.right_frame, text="", text_color="gray")
        self.lbl_profile_settings_sub.pack(anchor="w", padx=15, pady=(0, 10))

        self.lbl_cfg_exe = ctk.CTkLabel(self.right_frame, text=self.cfg.get_text("cfg_exe"))
        self.lbl_cfg_exe.pack(anchor="w", padx=15, pady=(5, 0))
        self.ent_exe = ctk.CTkEntry(self.right_frame)
        self.ent_exe.pack(fill="x", padx=15, pady=5)
        self.btn_browse_exe = ctk.CTkButton(self.right_frame, text=self.cfg.get_text("btn_browse"), command=lambda: self.browse_path(self.ent_exe, is_file=True))
        self.btn_browse_exe.pack(anchor="e", padx=15)

        self.lbl_cfg_paks = ctk.CTkLabel(self.right_frame, text=self.cfg.get_text("cfg_paks"))
        self.lbl_cfg_paks.pack(anchor="w", padx=15, pady=(15, 0))
        self.ent_paks = ctk.CTkEntry(self.right_frame)
        self.ent_paks.pack(fill="x", padx=15, pady=5)
        self.btn_browse_paks = ctk.CTkButton(self.right_frame, text=self.cfg.get_text("btn_browse"), command=lambda: self.browse_path(self.ent_paks, is_file=False))
        self.btn_browse_paks.pack(anchor="e", padx=15)

        self.chk_uuu_var = ctk.BooleanVar(value=False)
        self.chk_uuu = ctk.CTkCheckBox(
            self.right_frame,
            text=self.cfg.get_text("cfg_uuu"),
            variable=self.chk_uuu_var
        )
        self.chk_uuu.pack(anchor="w", padx=15, pady=(20, 0))


        self.btn_save = ctk.CTkButton(self.right_frame, text=self.cfg.get_text("btn_save"), command=self.save_profile_data, fg_color="#0078D7")
        self.btn_save.pack(fill="x", padx=15, pady=(20, 15))

    # ==================================================================
    # Profile list / selection
    # ==================================================================

    def update_profile_dropdown(self):
        # Fetch available profiles and update the dropdown menu
        profiles = ModLogic.get_profiles()
        if not profiles:
            self.combo_profiles.configure(values=["---"])
            self.combo_profiles.set("---")
        else:
            self.combo_profiles.configure(values=profiles)
            last = self.cfg.data.get("last_profile")
            if last in profiles:
                self.combo_profiles.set(last)
            else:
                self.combo_profiles.set(profiles[0])
                self.cfg.data["last_profile"] = profiles[0]
                self.cfg.save()
        self.refresh_profile_panel()

    def on_profile_change(self, selection):
        # Persist whatever is currently in the fields for the profile we're
        # LEAVING before switching - previously this data was only written
        # to disk when the user explicitly clicked "Guardar", so filling in
        # a profile and switching away (even just to look at another one)
        # silently threw the unsaved edits away.
        self._persist_profile_fields(self._current_profile)

        if selection != "---":
            self.cfg.data["last_profile"] = selection
            self.cfg.save()
        self.load_mods_list()
        self.refresh_profile_panel()

    def refresh_profile_panel(self):
        prof = self.combo_profiles.get()
        self.lbl_profile_settings_sub.configure(
            text=prof if prof != "---" else self.cfg.get_text("no_profile_panel_hint")
        )
        self.load_profile_data(prof)
        self._current_profile = prof

    def load_mods_list(self):
        # Cancel any pending auto-refresh before doing anything else, so
        # switching profiles/language doesn't stack up duplicate timers.
        if self._mods_poll_id is not None:
            self.after_cancel(self._mods_poll_id)
            self._mods_poll_id = None

        self.textbox_mods.configure(state="normal")
        self.textbox_mods.delete("0.0", "end")

        prof = self.combo_profiles.get()
        if prof == "---":
            self.textbox_mods.insert("end", self.cfg.get_text("no_mods"))
        else:
            mods_dir = os.path.join(PROFILES_DIR, prof, "Mods")
            if os.path.exists(mods_dir):
                mods = [f for f in os.listdir(mods_dir) if f.endswith('.pak')]
                if mods:
                    for m in mods:
                        self.textbox_mods.insert("end", f"📦 {m}\n")
                else:
                    self.textbox_mods.insert("end", self.cfg.get_text("no_mods"))

        self.textbox_mods.configure(state="disabled")

        # Refresh the UI list every 2 seconds automatically
        self._mods_poll_id = self.after(2000, self.load_mods_list)

    # ==================================================================
    # Profile folder / adding mods
    # ==================================================================

    def open_profile_folder(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            messagebox.showinfo(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_no_profile"))
            return
        if not ModLogic.open_profile_folder(prof):
            messagebox.showerror(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_open_folder"))

    def add_mods_dialog(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            messagebox.showinfo(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_no_profile"))
            return

        files = filedialog.askopenfilenames(filetypes=[("Mod files (.pak)", "*.pak")])
        if not files:
            return

        added, failed = ModLogic.add_mods_to_profile(prof, files)
        if added:
            self.load_mods_list()
        if failed:
            names = "\n".join(f"- {name}: {err}" for name, err in failed)
            messagebox.showwarning(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_copy_mods", files=names))

    # ==================================================================
    # Crash recovery
    # ==================================================================

    def _check_recovery(self):
        recovery = ModLogic.recover_pending_state()
        if recovery is None:
            return
        if recovery["recovered"]:
            messagebox.showinfo(
                self.cfg.get_text("recovered_title"),
                self.cfg.get_text("recovered_msg", count=len(recovery["recovered"]))
            )
            self.load_mods_list()
        elif recovery["failed"]:
            messagebox.showwarning(
                self.cfg.get_text("recovered_title"),
                self.cfg.get_text("recovery_failed_msg", profile=recovery.get("profile", ""))
            )

    # ==================================================================
    # Update check
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
        if messagebox.askyesno(
            self.cfg.get_text("update_title"),
            self.cfg.get_text("update_msg", latest=info["latest"], current=APP_VERSION),
        ):
            webbrowser.open(info["url"])

    # ==================================================================
    # Launching (non-blocking)
    # ==================================================================

    def play_game(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            messagebox.showinfo(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_no_profile"))
            return

        # Make sure Play uses whatever is currently shown in the fields,
        # even if "Guardar" was never explicitly clicked.
        self._persist_profile_fields(prof)

        self.btn_play.configure(state="disabled", text=self.cfg.get_text("status_playing"))
        self.withdraw()  # Hide the launcher window while playing

        threading.Thread(target=self._launch_worker, args=(prof,), daemon=True).start()
        self._poll_launch_result()

    def _launch_worker(self, profile_name):
        result = ModLogic.launch_game(profile_name)
        self._result_queue.put(result)

    def _poll_launch_result(self):
        try:
            result = self._result_queue.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_launch_result)
            return
        self._on_game_closed(result)

    def _on_game_closed(self, result):
        self.deiconify()
        self.btn_play.configure(state="normal", text=self.cfg.get_text("play"))

        if not result["success"]:
            messagebox.showerror(self.cfg.get_text("err_launch_title"), self._describe_error(result))
        else:
            failed = result["failed_in"] + result["failed_out"]
            if failed:
                names = ", ".join(name for name, _ in failed)
                messagebox.showwarning(
                    self.cfg.get_text("err_launch_title"),
                    self.cfg.get_text("err_partial_move", files=names)
                )

        self.load_mods_list()

    def _describe_error(self, result):
        err = result.get("error") or ""
        if err in ("missing_config", "missing_paths"):
            return self.cfg.get_text("err_fields")
        if err == "exe_not_found":
            return self.cfg.get_text("err_exe_missing")
        if err == "paks_not_found":
            return self.cfg.get_text("err_paks_missing")
        return self.cfg.get_text("err_launch_generic", error=err)

    # ==================================================================
    # Profile management (New / Delete / Save) - now all on the home screen
    # ==================================================================

    def create_new_profile(self):
        name = simpledialog.askstring(self.cfg.get_text("new_prof_title"), self.cfg.get_text("new_prof_msg"), parent=self)
        if not name:
            return
        name = INVALID_NAME_CHARS.sub('', name).strip().strip('.')
        if not name:
            messagebox.showerror("Error", self.cfg.get_text("invalid_profile_name"), parent=self)
            return

        prof_path = os.path.join(PROFILES_DIR, name)
        if os.path.exists(prof_path):
            messagebox.showerror("Error", self.cfg.get_text("err_exists"), parent=self)
            return

        try:
            os.makedirs(prof_path)
            os.makedirs(os.path.join(prof_path, "Mods"))
            with open(os.path.join(prof_path, "profile_config.json"), 'w', encoding='utf-8') as f:
                json.dump({"exe_path": "", "paks_path": ""}, f, indent=4)
        except OSError as e:
            messagebox.showerror("Error", str(e), parent=self)
            return

        self._persist_profile_fields(self._current_profile)  # don't lose edits on the profile we're leaving
        self.cfg.data["last_profile"] = name
        self.cfg.save()
        self.update_profile_dropdown()  # selects the new profile and refreshes the right panel
        self.load_mods_list()

    def delete_selected_profile(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            return

        confirmed = messagebox.askyesno(
            self.cfg.get_text("confirm_delete_title"),
            self.cfg.get_text("confirm_delete_msg", name=prof),
            parent=self
        )
        if not confirmed:
            return

        ModLogic.delete_profile(prof)

        if self.cfg.data.get("last_profile") == prof:
            self.cfg.data["last_profile"] = ""
            self.cfg.save()

        self.update_profile_dropdown()
        self.load_mods_list()

    def load_profile_data(self, profile_name):
        for ent in (self.ent_exe, self.ent_paks):
            ent.delete(0, 'end')

        if profile_name == "---":
            return

        cfg_file = os.path.join(PROFILES_DIR, profile_name, "profile_config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.ent_exe.insert(0, cfg.get("exe_path", ""))
                self.ent_paks.insert(0, cfg.get("paks_path", ""))
                self.chk_uuu_var.set(bool(cfg.get("use_uuu", False)))
            except (OSError, json.JSONDecodeError):
                pass

    def save_profile_data(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            messagebox.showinfo(self.cfg.get_text("err_launch_title"), self.cfg.get_text("err_no_profile"))
            return

        if not self.ent_exe.get().strip() or not self.ent_paks.get().strip():
            messagebox.showerror("Error", self.cfg.get_text("err_fields"))
            return

        self._persist_profile_fields(prof)
        self._flash_save_button()

    def _persist_profile_fields(self, profile_name):
        """
        Writes whatever is currently in the exe/paks fields to the given
        profile's config file - silently, with no validation and no popup.
        This is what keeps the right-hand panel and disk in sync: it runs
        automatically when switching profiles, launching the game, or
        closing the app, so in-progress edits are never lost just because
        "Guardar" wasn't clicked. The explicit Save button still validates
        the fields before calling this (see save_profile_data above).
        """
        if not profile_name or profile_name == "---":
            return
        prof_dir = os.path.join(PROFILES_DIR, profile_name)
        if not os.path.isdir(prof_dir):
            return  # profile was deleted/renamed since being selected
        cfg_file = os.path.join(prof_dir, "profile_config.json")
        try:
            existing = {}
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                except (OSError, json.JSONDecodeError):
                    existing = {}
            existing.update({
                "exe_path": self.ent_exe.get().strip(),
                "paks_path": self.ent_paks.get().strip(),
                "use_uuu": bool(self.chk_uuu_var.get()),
            })
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=4)
        except OSError:
            pass

    def _flash_save_button(self):
        # Brief non-blocking confirmation instead of a popup, since Save no
        # longer closes a dialog like it used to (there's no dialog anymore).
        original = self.cfg.get_text("btn_save")
        self.btn_save.configure(text="✓")
        self.after(1200, lambda: self.btn_save.configure(text=original))

    def browse_file(self, entry_widget, label, pattern):
        path = filedialog.askopenfilename(filetypes=[(label, pattern)])
        if path:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, path)

    def browse_path(self, entry_widget, is_file):
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe")]) if is_file else filedialog.askdirectory()
        if path:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, path)

    # ==================================================================
    # Settings (language only)
    # ==================================================================

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self.cfg.get_text("app_settings_title"))
        win.geometry("300x160")
        win.attributes("-topmost", True)
        self._set_window_icon(win)

        ctk.CTkLabel(win, text=self.cfg.get_text("lang"), font=ctk.CTkFont(weight="bold")).pack(pady=(25, 8))

        lang_var = ctk.StringVar(value=self.cfg.data.get("language", "en"))
        ctk.CTkOptionMenu(win, values=["en", "es"], variable=lang_var, command=self.change_language, width=140).pack()

    def change_language(self, selected_lang):
        self.cfg.data["language"] = selected_lang
        self.cfg.save()

        self.title(self.cfg.get_text("title"))
        self.lbl_title.configure(text=self.cfg.get_text("title"))
        self.btn_settings.configure(text=self.cfg.get_text("settings"))
        self.lbl_profile.configure(text=self.cfg.get_text("profile"))
        self.lbl_mods.configure(text=self.cfg.get_text("mods_list"))
        self.btn_play.configure(text=self.cfg.get_text("play"))
        self.btn_open_folder.configure(text=self.cfg.get_text("btn_open_folder"))
        self.btn_add_mods.configure(text=self.cfg.get_text("btn_add_mods"))
        self.btn_new_profile.configure(text=self.cfg.get_text("btn_new"))
        self.btn_delete_profile.configure(text=self.cfg.get_text("btn_delete"))
        self.lbl_profile_settings.configure(text=self.cfg.get_text("cfg_title"))
        self.lbl_cfg_exe.configure(text=self.cfg.get_text("cfg_exe"))
        self.lbl_cfg_paks.configure(text=self.cfg.get_text("cfg_paks"))
        self.btn_browse_exe.configure(text=self.cfg.get_text("btn_browse"))
        self.btn_browse_paks.configure(text=self.cfg.get_text("btn_browse"))
        self.btn_save.configure(text=self.cfg.get_text("btn_save"))
        self.chk_uuu.configure(text=self.cfg.get_text("cfg_uuu"))
        self.refresh_profile_panel()
        self.load_mods_list()

    def _on_close(self):
        # Don't lose in-progress edits just because the window was closed
        # instead of switching profiles or clicking "Guardar".
        self._persist_profile_fields(self._current_profile)
        self.destroy()


if __name__ == "__main__":
    app = ModLauncher()
    app.mainloop()
