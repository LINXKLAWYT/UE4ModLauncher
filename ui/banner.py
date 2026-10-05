"""
Barra de avisos dentro de la ventana.

Sustituye a los cuadros emergentes (messagebox): los mensajes de info,
éxito, advertencia y error, y las preguntas de confirmación ("¿Eliminar
perfil?", "¿Descargar actualización?"), se muestran en una franja encima del
contenido, sin abrir ninguna ventana aparte.

Solo se debe usar desde el hilo principal de Tk.
"""
import customtkinter as ctk

KIND_COLORS = {
    "info": "#1f538d",
    "success": "#1e7a3a",
    "warning": "#8a6d1a",
    "error": "#a71d2a",
    "question": "#2b3a55",
}
KIND_HOVER = {
    "info": "#173e6b",
    "success": "#165c2a",
    "warning": "#6b5412",
    "error": "#842030",
    "question": "#1f2a3f",
}
# Los avisos informativos se quitan solos; errores, advertencias y
# preguntas se quedan hasta que el usuario responda o los cierre.
AUTO_DISMISS_MS = {"info": 6000, "success": 4000}


class NotificationBar(ctk.CTkFrame):
    def __init__(self, master, before):
        super().__init__(master, corner_radius=8)
        self._before = before      # widget encima del cual se coloca la barra
        self._queue = []
        self._current = None
        self._timer = None

        self._buttons = ctk.CTkFrame(self, fg_color="transparent")
        self._buttons.pack(side="right", padx=(0, 10), pady=8)

        self._text_col = ctk.CTkFrame(self, fg_color="transparent")
        self._text_col.pack(side="left", fill="x", expand=True, padx=(14, 8), pady=8)

        self._title = ctk.CTkLabel(
            self._text_col, text="", anchor="w", justify="left",
            text_color="white", font=ctk.CTkFont(size=13, weight="bold"))
        self._msg = ctk.CTkLabel(
            self._text_col, text="", anchor="w", justify="left",
            text_color="white", wraplength=620)

    # ------------------------------------------------------------------

    def push(self, kind, text, title="", actions=None, sticky=False):
        """
        kind:    "info" | "success" | "warning" | "error" | "question"
        actions: lista de (texto_botón, callback_o_None). Al pulsar uno se
                 cierra el aviso y luego se ejecuta su callback.
        sticky:  True = no se quita solo aunque sea info/success.
        """
        item = {"kind": kind, "text": text, "title": title,
                "actions": actions or [], "sticky": sticky}
        cur = self._current
        replaceable = (cur is not None and cur["kind"] in AUTO_DISMISS_MS
                       and not cur["sticky"] and not cur["actions"])
        if cur is None or replaceable:
            self._show(item)
        else:
            self._queue.append(item)

    def dismiss(self):
        self._cancel_timer()
        self._current = None
        if self._queue:
            self._show(self._queue.pop(0))
        else:
            self.pack_forget()

    # ------------------------------------------------------------------

    def _show(self, item):
        self._cancel_timer()
        self._current = item
        kind = item["kind"]
        self.configure(fg_color=KIND_COLORS.get(kind, KIND_COLORS["info"]))

        self._title.pack_forget()
        self._msg.pack_forget()
        if item["title"]:
            self._title.configure(text=item["title"])
            self._title.pack(anchor="w")
        self._msg.configure(text=item["text"])
        self._msg.pack(anchor="w")

        for child in self._buttons.winfo_children():
            child.destroy()
        if item["actions"]:
            for label, callback in item["actions"]:
                ctk.CTkButton(
                    self._buttons, text=label, width=90, height=28,
                    fg_color="#ffffff", text_color="#111111", hover_color="#d9d9d9",
                    command=lambda cb=callback: self._on_action(cb),
                ).pack(side="left", padx=(6, 0))
        else:
            ctk.CTkButton(
                self._buttons, text="✕", width=30, height=28,
                fg_color="transparent", hover_color=KIND_HOVER.get(kind, "#173e6b"),
                command=self.dismiss,
            ).pack()

        self.pack(fill="x", padx=20, pady=(0, 10), before=self._before)

        ms = AUTO_DISMISS_MS.get(kind)
        if ms and not item["sticky"] and not item["actions"]:
            self._timer = self.after(ms, self.dismiss)

    def _on_action(self, callback):
        self.dismiss()          # primero cerrar, por si el callback lanza otro aviso
        if callback is not None:
            callback()

    def _cancel_timer(self):
        if self._timer is not None:
            try:
                self.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None
