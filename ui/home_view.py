"""
Pantalla principal: perfiles, lista de mods, botón de jugar y ajustes del
perfil seleccionado. Crear y eliminar perfiles se hace aquí mismo, con un
formulario y una confirmación dentro de la ventana (sin cuadros emergentes).
"""
import json
import os
import queue
import re
import threading

import customtkinter as ctk
from tkinter import filedialog

import config
from core import ModLogic

INVALID_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


class HomeView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.cfg = app.cfg

        self._result_queue = queue.Queue()  # hilo de juego -> hilo principal
        self._current_profile = None        # perfil cuyos campos se ven a la derecha
        self._mod_vars = {}                  # selección de mods por perfil
        self._rendered_mod_names = None

        self.left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.right_frame = ctk.CTkFrame(self, width=300)
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.pack_propagate(False)  # ancho fijo

        self._build_left_panel()
        self._build_right_panel()

        self.update_profile_dropdown()
        self.load_mods_list()

    def t(self, key, **kwargs):
        return self.cfg.get_text(key, **kwargs)

    # ==================================================================
    # Construcción de la interfaz
    # ==================================================================

    def _build_left_panel(self):
        self.prof_frame = ctk.CTkFrame(self.left_frame)
        self.prof_frame.pack(fill="x", pady=(0, 10))

        self.lbl_profile = ctk.CTkLabel(self.prof_frame, text=self.t("profile"), font=ctk.CTkFont(weight="bold"))
        self.lbl_profile.pack(anchor="w", padx=15, pady=(10, 0))

        self.prof_row = ctk.CTkFrame(self.prof_frame, fg_color="transparent")
        self.prof_row.pack(fill="x", padx=15, pady=(5, 10))

        self.combo_profiles = ctk.CTkOptionMenu(self.prof_row, values=["---"], command=self.on_profile_change, width=170)
        self.combo_profiles.pack(side="left")

        self.btn_new_profile = ctk.CTkButton(self.prof_row, text=self.t("btn_new"), width=80, command=self.start_new_profile)
        self.btn_new_profile.pack(side="left", padx=(8, 0))

        self.btn_delete_profile = ctk.CTkButton(self.prof_row, text=self.t("btn_delete"), width=90, fg_color="#a71d2a", hover_color="#842030", command=self.delete_selected_profile)
        self.btn_delete_profile.pack(side="left", padx=(8, 0))

        # Formulario "nuevo perfil": oculto hasta pulsar "Nuevo".
        self.new_row = ctk.CTkFrame(self.prof_frame, fg_color="transparent")
        self.ent_new_name = ctk.CTkEntry(self.new_row, placeholder_text=self.t("new_prof_placeholder"), width=170)
        self.ent_new_name.pack(side="left")
        self.ent_new_name.bind("<Return>", lambda e: self.create_new_profile())
        self.ent_new_name.bind("<Escape>", lambda e: self.cancel_new_profile())
        self.btn_new_ok = ctk.CTkButton(self.new_row, text=self.t("btn_create"), width=80, command=self.create_new_profile)
        self.btn_new_ok.pack(side="left", padx=(8, 0))
        self.btn_new_cancel = ctk.CTkButton(self.new_row, text=self.t("btn_cancel"), width=90, fg_color="gray30", hover_color="gray25", command=self.cancel_new_profile)
        self.btn_new_cancel.pack(side="left", padx=(8, 0))

        self.mods_row = ctk.CTkFrame(self.prof_frame, fg_color="transparent")
        self.mods_row.pack(fill="x", padx=15, pady=(0, 10))

        self.btn_open_folder = ctk.CTkButton(self.mods_row, text=self.t("btn_open_folder"), width=100, command=self.open_profile_folder)
        self.btn_open_folder.pack(side="left")

        self.btn_add_mods = ctk.CTkButton(self.mods_row, text=self.t("btn_add_mods"), width=150, command=self.add_mods_dialog)
        self.btn_add_mods.pack(side="left", padx=(8, 0))

        self.btn_refresh_mods = ctk.CTkButton(
            self.mods_row, text=self.t("btn_refresh_mods"), width=130, command=self.load_mods_list
        )
        self.btn_refresh_mods.pack(side="left", padx=(8, 0))

        self.mods_frame = ctk.CTkFrame(self.left_frame)
        self.mods_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.lbl_mods = ctk.CTkLabel(self.mods_frame, text=self.t("mods_list"))
        self.lbl_mods.pack(anchor="w", padx=15, pady=(10, 5))

        self.mods_checklist = ctk.CTkScrollableFrame(self.mods_frame, fg_color="#1e1e1e")
        self.mods_checklist.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.lbl_mod_hint = ctk.CTkLabel(self.mods_frame, text=self.t("mods_selection_hint"), text_color="gray")
        self.lbl_mod_hint.pack(anchor="w", padx=15, pady=(0, 8))

        self.btn_play = ctk.CTkButton(self.left_frame, text=self.t("play"), height=50, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#28a745", hover_color="#218838", command=self.play_game)
        self.btn_play.pack(fill="x")

    def _build_right_panel(self):
        self.lbl_profile_settings = ctk.CTkLabel(self.right_frame, text=self.t("cfg_title"), font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_profile_settings.pack(anchor="w", padx=15, pady=(15, 0))

        self.lbl_profile_settings_sub = ctk.CTkLabel(self.right_frame, text="", text_color="gray")
        self.lbl_profile_settings_sub.pack(anchor="w", padx=15, pady=(0, 10))

        self.lbl_cfg_exe = ctk.CTkLabel(self.right_frame, text=self.t("cfg_exe"))
        self.lbl_cfg_exe.pack(anchor="w", padx=15, pady=(5, 0))
        self.ent_exe = ctk.CTkEntry(self.right_frame)
        self.ent_exe.pack(fill="x", padx=15, pady=5)
        self.btn_browse_exe = ctk.CTkButton(self.right_frame, text=self.t("btn_browse"), command=lambda: self.browse_path(self.ent_exe, is_file=True))
        self.btn_browse_exe.pack(anchor="e", padx=15)

        self.lbl_cfg_paks = ctk.CTkLabel(self.right_frame, text=self.t("cfg_paks"))
        self.lbl_cfg_paks.pack(anchor="w", padx=15, pady=(15, 0))
        self.ent_paks = ctk.CTkEntry(self.right_frame)
        self.ent_paks.pack(fill="x", padx=15, pady=5)
        self.btn_browse_paks = ctk.CTkButton(self.right_frame, text=self.t("btn_browse"), command=lambda: self.browse_path(self.ent_paks, is_file=False))
        self.btn_browse_paks.pack(anchor="e", padx=15)

        self.chk_uuu_var = ctk.BooleanVar(value=False)
        self.chk_uuu = ctk.CTkCheckBox(self.right_frame, text=self.t("cfg_uuu"), variable=self.chk_uuu_var,
                                       command=self._update_uuu_visibility)
        self.chk_uuu.pack(anchor="w", padx=15, pady=(20, 0))

        # Ajustes del UUU: solo se muestran con el UUU activado. Los widgets
        # existen siempre, así la ruta guardada se conserva aunque esté oculto.
        self.uuu_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.lbl_cfg_uuu_dll = ctk.CTkLabel(self.uuu_frame, text=self.t("cfg_uuu_dll"))
        self.lbl_cfg_uuu_dll.pack(anchor="w", padx=15, pady=(10, 0))
        self.ent_uuu_dll = ctk.CTkEntry(self.uuu_frame)
        self.ent_uuu_dll.pack(fill="x", padx=15, pady=5)
        self.btn_browse_uuu_dll = ctk.CTkButton(self.uuu_frame, text=self.t("btn_browse"), command=lambda: self.browse_dll(self.ent_uuu_dll))
        self.btn_browse_uuu_dll.pack(anchor="e", padx=15)

        self.btn_save = ctk.CTkButton(self.right_frame, text=self.t("btn_save"), command=self.save_profile_data, fg_color="#0078D7")
        self.btn_save.pack(fill="x", padx=15, pady=(20, 15))

    # ==================================================================
    # Lista de perfiles / selección
    # ==================================================================

    def update_profile_dropdown(self):
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
        # Guardar lo que hay en los campos del perfil que se abandona,
        # para no perder cambios sin guardar al cambiar de perfil.
        self._persist_profile_fields(self._current_profile)

        if selection != "---":
            self.cfg.data["last_profile"] = selection
            self.cfg.save()
        self.load_mods_list()
        self.refresh_profile_panel()

    def refresh_profile_panel(self):
        prof = self.combo_profiles.get()
        self.lbl_profile_settings_sub.configure(
            text=prof if prof != "---" else self.t("no_profile_panel_hint")
        )
        self.load_profile_data(prof)
        self._current_profile = prof

    def load_mods_list(self):
        # La lista se actualiza solo al abrir/cambiar de perfil, al añadir mods
        # o cuando el usuario pulsa "Recargar mods". No hay polling automático.

        prof = self.combo_profiles.get()
        mods_dir = os.path.join(config.PROFILES_DIR, prof, "Mods") if prof != "---" else ""
        try:
            mods = sorted(f for f in os.listdir(mods_dir) if f.lower().endswith('.pak')) if os.path.isdir(mods_dir) else []
        except OSError:
            mods = []

        # Leer la selección guardada para este perfil. Si es un perfil antiguo
        # sin selección guardada, todos los mods quedan activados por defecto.
        selected = None
        if prof != "---":
            cfg_file = os.path.join(config.PROFILES_DIR, prof, "profile_config.json")
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    profile_cfg = json.load(f)
                selected = profile_cfg.get("selected_mods")
            except (OSError, json.JSONDecodeError):
                pass

        signature = (prof, tuple(mods))
        if signature != self._rendered_mod_names:
            for child in self.mods_checklist.winfo_children():
                child.destroy()
            self._mod_vars = {}
            if prof == "---" or not mods:
                ctk.CTkLabel(self.mods_checklist, text=self.t("no_mods")).pack(anchor="w", padx=8, pady=8)
            else:
                for name in mods:
                    var = ctk.BooleanVar(value=(name in selected if selected is not None else True))
                    self._mod_vars[name] = var
                    ctk.CTkCheckBox(
                        self.mods_checklist, text=name, variable=var,
                        command=self.save_mod_selection
                    ).pack(anchor="w", padx=8, pady=5)
            self._rendered_mod_names = signature


    def save_mod_selection(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            return
        cfg_file = os.path.join(config.PROFILES_DIR, prof, "profile_config.json")
        try:
            existing = {}
            if os.path.isfile(cfg_file):
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            existing["selected_mods"] = [name for name, var in self._mod_vars.items() if var.get()]
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=4)
        except (OSError, json.JSONDecodeError) as e:
            self.app.notify("error", f"No se pudo guardar la selección de mods: {e}", title=self.t("err_title"))

    # ==================================================================
    # Carpeta del perfil / añadir mods
    # ==================================================================

    def open_profile_folder(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            self.app.notify("info", self.t("err_no_profile"), title=self.t("err_launch_title"))
            return
        if not ModLogic.open_profile_folder(prof):
            self.app.notify("error", self.t("err_open_folder"), title=self.t("err_launch_title"))

    def add_mods_dialog(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            self.app.notify("info", self.t("err_no_profile"), title=self.t("err_launch_title"))
            return

        # Selector de archivos del sistema: es el único diálogo que queda,
        # porque es el propio explorador de Windows.
        files = filedialog.askopenfilenames(filetypes=[("Mod files (.pak)", "*.pak")])
        if not files:
            return

        added, failed = ModLogic.add_mods_to_profile(prof, files)
        if added:
            self.load_mods_list()
        if failed:
            names = "\n".join(f"- {name}: {err}" for name, err in failed)
            self.app.notify("warning", self.t("err_copy_mods", files=names), title=self.t("err_launch_title"))

    # ==================================================================
    # Lanzar el juego (sin bloquear la interfaz)
    # ==================================================================

    def play_game(self):
        if getattr(self.app, "migrating", False):
            self.app.notify("info", self.t("loc_busy"), title=self.t("err_launch_title"))
            return
        prof = self.combo_profiles.get()
        if prof == "---":
            self.app.notify("info", self.t("err_no_profile"), title=self.t("err_launch_title"))
            return

        if not self._uuu_selection_ok():
            self.app.notify("error", self.t("err_uuu_dll"), title=self.t("err_launch_title"))
            return

        # Jugar usa lo que se ve en los campos aunque no se pulsara "Guardar".
        self._persist_profile_fields(prof)

        self.btn_play.configure(state="disabled", text=self.t("status_playing"))
        self.app.withdraw()  # ocultar el launcher mientras se juega

        threading.Thread(target=self._launch_worker, args=(prof,), daemon=True).start()
        self._poll_launch_result()

    def _launch_worker(self, profile_name):
        self._result_queue.put(ModLogic.launch_game(profile_name))

    def _poll_launch_result(self):
        try:
            result = self._result_queue.get_nowait()
        except queue.Empty:
            self.after(200, self._poll_launch_result)
            return
        self._on_game_closed(result)

    def _on_game_closed(self, result):
        self.app.deiconify()
        self.btn_play.configure(state="normal", text=self.t("play"))

        if not result["success"]:
            self.app.notify("error", self._describe_error(result), title=self.t("err_launch_title"))
        else:
            failed = result["failed_in"] + result["failed_out"]
            if failed:
                names = ", ".join(name for name, _ in failed)
                self.app.notify("warning", self.t("err_partial_move", files=names), title=self.t("err_launch_title"))

        self.load_mods_list()

    def _describe_error(self, result):
        err = result.get("error") or ""
        if err in ("missing_config", "missing_paths"):
            return self.t("err_fields")
        if err == "exe_not_found":
            return self.t("err_exe_missing")
        if err == "paks_not_found":
            return self.t("err_paks_missing")
        return self.t("err_launch_generic", error=err)

    # ==================================================================
    # Gestión de perfiles: Nuevo / Eliminar / Guardar (todo en pantalla)
    # ==================================================================

    def start_new_profile(self):
        """Muestra el formulario de nombre dentro del panel de perfiles."""
        if not self.new_row.winfo_ismapped():
            self.new_row.pack(fill="x", padx=15, pady=(0, 10), after=self.prof_row)
        self.ent_new_name.focus_set()

    def cancel_new_profile(self):
        self.new_row.pack_forget()
        self.ent_new_name.delete(0, "end")

    def create_new_profile(self):
        raw = self.ent_new_name.get()
        if not raw.strip():
            return  # nada escrito: el formulario sigue abierto
        name = INVALID_NAME_CHARS.sub('', raw).strip().strip('.')
        if not name:
            self.app.notify("error", self.t("invalid_profile_name"), title=self.t("err_title"))
            return

        prof_path = os.path.join(config.PROFILES_DIR, name)
        if os.path.exists(prof_path):
            self.app.notify("error", self.t("err_exists"), title=self.t("err_title"))
            return

        try:
            os.makedirs(prof_path)
            os.makedirs(os.path.join(prof_path, "Mods"))
            with open(os.path.join(prof_path, "profile_config.json"), 'w', encoding='utf-8') as f:
                json.dump({"exe_path": "", "paks_path": ""}, f, indent=4)
        except OSError as e:
            self.app.notify("error", str(e), title=self.t("err_title"))
            return

        self.cancel_new_profile()
        self._persist_profile_fields(self._current_profile)  # no perder cambios del perfil que se deja
        self.cfg.data["last_profile"] = name
        self.cfg.save()
        self.update_profile_dropdown()  # selecciona el nuevo perfil y refresca el panel derecho
        self.load_mods_list()
        self.app.notify("success", self.t("profile_created", name=name))

    def delete_selected_profile(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            return
        # Confirmación dentro de la ventana, en vez de un cuadro emergente.
        self.app.confirm(
            self.t("confirm_delete_msg", name=prof),
            on_yes=lambda: self._do_delete_profile(prof),
            title=self.t("confirm_delete_title"),
            yes_label=self.t("btn_delete_confirm"),
        )

    def _do_delete_profile(self, prof):
        ModLogic.delete_profile(prof)

        if self.cfg.data.get("last_profile") == prof:
            self.cfg.data["last_profile"] = ""
            self.cfg.save()
        if self._current_profile == prof:
            self._current_profile = None  # ya no existe: no intentar guardar sus campos

        self.update_profile_dropdown()
        self.load_mods_list()
        self.app.notify("success", self.t("profile_deleted", name=prof))

    def _update_uuu_visibility(self):
        """Muestra el panel de configuración del UUU solo si está activado."""
        if self.chk_uuu_var.get():
            if not self.uuu_frame.winfo_ismapped():
                self.uuu_frame.pack(fill="x", after=self.chk_uuu)
        else:
            self.uuu_frame.pack_forget()

    def load_profile_data(self, profile_name):
        for ent in (self.ent_exe, self.ent_paks, self.ent_uuu_dll):
            ent.delete(0, 'end')
        self.chk_uuu_var.set(False)

        if profile_name == "---":
            self._update_uuu_visibility()
            return

        cfg_file = os.path.join(config.PROFILES_DIR, profile_name, "profile_config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.ent_exe.insert(0, cfg.get("exe_path", ""))
                self.ent_paks.insert(0, cfg.get("paks_path", ""))
                self.ent_uuu_dll.insert(0, cfg.get("uuu_dll_path", ""))
                self.chk_uuu_var.set(bool(cfg.get("use_uuu", False)))
            except (OSError, json.JSONDecodeError):
                pass
        self._update_uuu_visibility()

    def save_profile_data(self):
        prof = self.combo_profiles.get()
        if prof == "---":
            self.app.notify("info", self.t("err_no_profile"), title=self.t("err_launch_title"))
            return

        if not self.ent_exe.get().strip() or not self.ent_paks.get().strip():
            self.app.notify("error", self.t("err_fields"), title=self.t("err_title"))
            return

        if not self._uuu_selection_ok():
            self.app.notify("error", self.t("err_uuu_dll"), title=self.t("err_title"))
            return

        self._persist_profile_fields(prof)
        self._flash_save_button()

    def _uuu_selection_ok(self):
        """True si el UUU está desactivado, o si está activado y se ha
        seleccionado un .dll real desde la app (el launcher no lo incluye
        ni lo busca en ninguna carpeta)."""
        if not self.chk_uuu_var.get():
            return True
        path = self.ent_uuu_dll.get().strip()
        return os.path.isfile(path) and path.lower().endswith(".dll")

    def persist(self):
        """Guarda los campos del perfil visible (al cambiar de pantalla o cerrar)."""
        self._persist_profile_fields(self._current_profile)

    def _persist_profile_fields(self, profile_name):
        """
        Escribe en el perfil lo que hay ahora en los campos, sin validar y
        sin avisos. Se ejecuta al cambiar de perfil, al jugar, al abrir
        Ajustes y al cerrar la app, para no perder cambios aunque no se
        pulsara "Guardar".
        """
        if not profile_name or profile_name == "---":
            return
        prof_dir = os.path.join(config.PROFILES_DIR, profile_name)
        if not os.path.isdir(prof_dir):
            return  # el perfil se eliminó desde que se seleccionó
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
                "uuu_dll_path": self.ent_uuu_dll.get().strip(),
            })
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, indent=4)
        except OSError:
            pass

    def _flash_save_button(self):
        original = self.t("btn_save")
        self.btn_save.configure(text="✓")
        self.after(1200, lambda: self.btn_save.configure(text=original))

    def browse_path(self, entry_widget, is_file):
        # Selector de archivos/carpetas del sistema (explorador de Windows).
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe")]) if is_file else filedialog.askdirectory()
        if path:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, path)

    def browse_dll(self, entry_widget):
        # Selector de archivos del sistema, filtrado a .dll.
        path = filedialog.askopenfilename(filetypes=[("DLL", "*.dll")])
        if path:
            entry_widget.delete(0, 'end')
            entry_widget.insert(0, path)

    # ==================================================================
    # Idioma
    # ==================================================================

    def apply_language(self):
        t = self.t
        self.lbl_profile.configure(text=t("profile"))
        self.lbl_mods.configure(text=t("mods_list"))
        self.btn_play.configure(text=t("play"))
        self.btn_open_folder.configure(text=t("btn_open_folder"))
        self.btn_add_mods.configure(text=t("btn_add_mods"))
        self.btn_refresh_mods.configure(text=t("btn_refresh_mods"))
        self.lbl_mod_hint.configure(text=t("mods_selection_hint"))
        self.btn_new_profile.configure(text=t("btn_new"))
        self.btn_delete_profile.configure(text=t("btn_delete"))
        self.btn_new_ok.configure(text=t("btn_create"))
        self.btn_new_cancel.configure(text=t("btn_cancel"))
        self.ent_new_name.configure(placeholder_text=t("new_prof_placeholder"))
        self.lbl_profile_settings.configure(text=t("cfg_title"))
        self.lbl_cfg_exe.configure(text=t("cfg_exe"))
        self.lbl_cfg_paks.configure(text=t("cfg_paks"))
        self.btn_browse_exe.configure(text=t("btn_browse"))
        self.btn_browse_paks.configure(text=t("btn_browse"))
        self.btn_save.configure(text=t("btn_save"))
        self.chk_uuu.configure(text=t("cfg_uuu"))
        self.lbl_cfg_uuu_dll.configure(text=t("cfg_uuu_dll"))
        self.btn_browse_uuu_dll.configure(text=t("btn_browse"))
        self.refresh_profile_panel()
        self.load_mods_list()
